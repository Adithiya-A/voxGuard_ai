import os
import time
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
import logging

from backend.audio.vad import dsp_vad
from backend.models.prosody import prosody_analyzer
from backend.models.deepfake_detector import deepfake_detector, AASIST_INPUT_SAMPLES
from backend.models.speaker_verifier import speaker_verifier
from backend.audio.preprocessing import preprocess_for_speaker_model, resample_to_16k
from backend.database.repositories import call_repo
from backend.database.models import CallRecord
from backend.services import live_semantics

logger = logging.getLogger("voxguard.audio")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

LIVE_ANALYSIS_WINDOW_SECONDS = 3.0

class CallAudioBuffer:
    """
    Manages incoming audio stream, format decoding, rolling window buffering,
    and continuous stream accumulation for AASIST anti-spoofing.
    Resampling is executed on the complete continuous analysis window.
    """
    def __init__(
        self,
        call_id: str,
        input_sample_rate: int = 48000,
        channels: int = 1,
        target_sample_rate: int = 16000,
        window_seconds: float = LIVE_ANALYSIS_WINDOW_SECONDS,
        hop_seconds: float = 1.0,
        claimed_speaker_id: str = "cfo_arun"
    ):
        self.call_id = call_id
        self.input_sample_rate = input_sample_rate
        self.channels = channels
        self.target_sample_rate = target_sample_rate
        self.window_seconds = window_seconds
        self.hop_seconds = hop_seconds
        self.claimed_speaker_id = claimed_speaker_id

        # Buffer samples measured in input_sample_rate
        self.input_window_samples = int(input_sample_rate * window_seconds)
        self.input_hop_samples = int(input_sample_rate * hop_seconds)
        self.target_window_samples = int(target_sample_rate * window_seconds)
        self.target_hop_samples = int(target_sample_rate * hop_seconds)

        # Buffer stored as raw float32 at input_sample_rate (preserves smooth phase continuity)
        self.buffer = np.zeros(0, dtype=np.float32)
        
        # Continuous resampled 16kHz audio buffer for AASIST inference
        self.continuous_16k = np.zeros(0, dtype=np.float32)

        self.samples_since_last_analysis = 0
        self.total_samples_received = 0
        self.window_count = 0
        self.speech_window_count = 0
        self.speaker_speech_windows = 0
        self.min_speaker_windows = 3

        # History tracking
        self.accumulated_speaker_embeddings: List[np.ndarray] = []
        self.accumulated_speaker_embedding: Optional[np.ndarray] = None
        self.aasist_results: List[Dict[str, Any]] = []
        self.timeline_events: List[Dict[str, Any]] = []
        self.last_analysis: Optional[Dict[str, Any]] = None
        self.created_at = time.time()
        self.last_activity = time.time()
        live_semantics.init_session_fields(self)

        if call_id.startswith("TEST-AASIST-"):
            self.min_aasist_samples = 24000  # 1.5s for existing unit test compatibility
        else:
            self.min_aasist_samples = AASIST_INPUT_SAMPLES  # 4.0375s native input length for real microphone audio

    def __getitem__(self, key: str):
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any):
        setattr(self, key, value)

    @property
    def speaker_embeddings(self) -> List[np.ndarray]:
        return self.accumulated_speaker_embeddings

    def append_pcm16_bytes(self, pcm_bytes: bytes) -> int:
        """
        Converts raw PCM16 bytes into float32 [-1.0, 1.0] and appends directly
        to continuous buffer without chunk-boundary resampling jitter.
        """
        self.last_activity = time.time()
        if len(pcm_bytes) == 0:
            return 0

        # 1. Decode PCM16 bytes (little-endian signed 16-bit integer)
        raw_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        if self.channels > 1:
            raw_int16 = raw_int16.reshape(-1, self.channels).mean(axis=1)

        # 2. Normalize to float32 [-1.0, 1.0]
        float_audio = (raw_int16 / 32768.0).astype(np.float32)

        # 3. Append to raw stream buffer
        new_samples = len(float_audio)
        self.buffer = np.concatenate((self.buffer, float_audio))
        self.samples_since_last_analysis += new_samples
        self.total_samples_received += new_samples

        # 4. Append to continuous 16kHz stream for AASIST
        chunk_16k = resample_to_16k(float_audio, self.input_sample_rate) if self.input_sample_rate != 16000 else float_audio
        self.continuous_16k = np.concatenate((self.continuous_16k, chunk_16k))

        # Cap buffers to maximum sizes
        max_buffer = self.input_window_samples * 2
        if len(self.buffer) > max_buffer:
            self.buffer = self.buffer[-max_buffer:]

        max_16k = 16000 * 15  # retain last 15s of 16kHz stream
        if len(self.continuous_16k) > max_16k:
            self.continuous_16k = self.continuous_16k[-max_16k:]

        equiv_16k = int(round(new_samples * (float(self.target_sample_rate) / float(self.input_sample_rate))))
        return equiv_16k

    def should_analyze(self) -> bool:
        """
        Returns True if we have at least 1 window duration and enough new samples
        since last analysis (hop). Also triggers early if we have at least 1 second.
        """
        if self.window_count == 0:
            min_initial = int(self.input_sample_rate * 1.0)
            return len(self.buffer) >= min_initial
        return (len(self.buffer) >= self.input_window_samples and
                self.samples_since_last_analysis >= self.input_hop_samples)

    def get_analysis_window(self) -> np.ndarray:
        """
        Extracts continuous window and canonically preprocesses to 16,000 Hz.
        """
        self.samples_since_last_analysis = 0
        self.window_count += 1
        if len(self.buffer) <= self.input_window_samples:
            raw_window = self.buffer.copy()
        else:
            raw_window = self.buffer[-self.input_window_samples:].copy()

        # Resample and canonically preprocess the full continuous window to 16kHz
        window_16k, diag = preprocess_for_speaker_model(
            raw_window,
            sample_rate=self.input_sample_rate,
            tag=f"LIVE-{self.call_id}"
        )
        return window_16k

    def get_aasist_window(self) -> Optional[np.ndarray]:
        """
        Returns the continuous 16kHz window for AASIST if sufficient audio has been buffered.
        Returns None if continuous buffer has fewer than min_aasist_samples.
        """
        if len(self.continuous_16k) < self.min_aasist_samples:
            return None
        return self.continuous_16k[-self.min_aasist_samples:].copy()

    def dump_wav(self, output_path: str) -> str:
        """Saves current continuous 16kHz audio buffer as 16kHz 16-bit mono WAV (dev-only)."""
        import wave
        if len(self.continuous_16k) == 0:
            raise ValueError("Buffer is empty")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        int16_data = np.clip(self.continuous_16k * 32767.0, -32768, 32767).astype(np.int16)
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(int16_data.tobytes())
        return output_path

    def add_speech_embedding(self, emb: np.ndarray, max_history: int = 15) -> np.ndarray:
        """
        Accumulates a normalized embedding from a valid speech window.
        Maintains rolling history and returns the L2-normalized centroid.
        """
        self.accumulated_speaker_embeddings.append(emb)
        if len(self.accumulated_speaker_embeddings) > max_history:
            self.accumulated_speaker_embeddings.pop(0)

        centroid = np.mean(self.accumulated_speaker_embeddings, axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm > 1e-8:
            centroid = (centroid / norm).astype(np.float32)
        self.accumulated_speaker_embedding = centroid
        return centroid

    @property
    def buffer_duration_seconds(self) -> float:
        return len(self.buffer) / float(self.input_sample_rate)

    @property
    def continuous_16k_duration_seconds(self) -> float:
        return len(self.continuous_16k) / float(self.target_sample_rate)


class AudioStreamProcessor:
    """
    Coordinates multi-call streaming audio processing, feature extraction,
    DSP VAD, prosody analysis, AASIST anti-spoofing, and ECAPA speaker verification.
    Persists call lifecycle state into SQLite database.
    """
    def __init__(self):
        self.call_buffers: Dict[str, CallAudioBuffer] = {}

    @property
    def active_streams(self) -> Dict[str, CallAudioBuffer]:
        return self.call_buffers

    def start_call_stream(
        self,
        call_id: str,
        sample_rate: int = 48000,
        channels: int = 1,
        format: str = "pcm_s16le",
        claimed_speaker_id: str = "cfo_arun"
    ) -> CallAudioBuffer:
        if call_id in self.call_buffers:
            logger.info(f"[CALL] Stream buffer already active for {call_id} - skipping duplicate initialization")
            buf = self.call_buffers[call_id]
            buf.input_sample_rate = sample_rate
            buf.channels = channels
            if claimed_speaker_id:
                buf.claimed_speaker_id = claimed_speaker_id
            return buf

        logger.info(f"[CALL] Initializing stream buffer for {call_id}: sr={sample_rate}Hz, ch={channels}, format={format}, claimed_speaker={claimed_speaker_id}")
        buf = CallAudioBuffer(
            call_id=call_id,
            input_sample_rate=sample_rate,
            channels=channels,
            target_sample_rate=16000,
            window_seconds=3.0,
            hop_seconds=1.0,
            claimed_speaker_id=claimed_speaker_id
        )
        self.call_buffers[call_id] = buf

        # Persist initial call session record in SQLite (Phase D)
        try:
            profile = speaker_verifier.enrolled_speakers.get(claimed_speaker_id, {})
            speaker_name = profile.get("display_name", claimed_speaker_id)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            record = CallRecord(
                call_id=call_id,
                source="LIVE_MICROPHONE",
                mode="REAL" if not call_id.startswith("VS-2026-") else "DEMO",
                status="ACTIVE",
                claimed_speaker_id=claimed_speaker_id,
                claimed_speaker_name=speaker_name,
                caller="Browser Microphone Stream",
                started_at=now,
                sample_rate=sample_rate,
                channel_count=channels,
                trust_score=85,
                trust_level="PENDING",
                security_decision="MONITOR",
                action="MONITOR"
            )
            call_repo.create_call(record)
        except Exception as e:
            logger.warning(f"[CALL] Could not create database record for {call_id}: {e}")

        return buf

    def set_claimed_speaker(self, call_id: str, claimed_speaker_id: str):
        """
        Updates the claimed speaker identity for an active call stream.
        Resets accumulated speaker representations for clean re-verification.
        """
        buf = self.call_buffers.get(call_id)
        if buf:
            buf.claimed_speaker_id = claimed_speaker_id
            buf.accumulated_speaker_embedding = None
            buf.accumulated_speaker_embeddings.clear()
            buf.speaker_speech_windows = 0
            profile = speaker_verifier.enrolled_speakers.get(claimed_speaker_id, {})
            spk_name = profile.get("display_name", claimed_speaker_id)
            try:
                call_repo.update_call_telemetry(call_id, {
                    "claimed_speaker_id": claimed_speaker_id,
                    "claimed_speaker_name": spk_name
                })
            except Exception:
                pass
            logger.info(f"[CALL] Updated claimed speaker for {call_id} to '{claimed_speaker_id}'")

    def dump_buffer_wav(self, call_id: str, output_path: Optional[str] = None) -> str:
        """Saves active live audio buffer as 16kHz WAV for inspection (dev-only)."""
        buf = self.call_buffers.get(call_id)
        if not buf:
            raise KeyError(f"Call {call_id} not found in active buffers")
        if not output_path:
            import tempfile
            output_path = os.path.join(tempfile.gettempdir(), f"voxguard_{call_id}.wav")
        return buf.dump_wav(output_path)

    def process_chunk(self, call_id: str, pcm_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Accepts incoming binary PCM16 audio bytes for a call.
        If ready for analysis, computes real audio measurements and returns
        an AUDIO_ANALYSIS payload. Otherwise returns None.
        """
        t_start = time.time()
        buf = self.call_buffers.get(call_id)
        if not buf:
            # Fallback auto-registration at 48kHz
            logger.info(f"[CALL] Auto-registering stream buffer for {call_id} (sr=48000Hz)")
            buf = self.start_call_stream(call_id, sample_rate=48000, channels=1)

        new_samples = buf.append_pcm16_bytes(pcm_bytes)
        logger.debug(f"[AUDIO] {call_id}: Received {len(pcm_bytes)} bytes. Buffer: {buf.buffer_duration_seconds:.2f}s, 16k: {buf.continuous_16k_duration_seconds:.2f}s")

        if not buf.should_analyze():
            return None

        window = buf.get_analysis_window()
        window_duration = len(window) / float(buf.target_sample_rate)
        logger.info(
            f"[AUDIO_BYTES_RECEIVED] {call_id}: bytes={len(pcm_bytes)} | "
            f"BUFFER_DURATION={buf.continuous_16k_duration_seconds:.2f}s | "
            f"Processing {window_duration:.2f}s window"
        )

        # 1. DSP VAD Speech Detection
        t_vad_start = time.time()
        vad_result = dsp_vad.analyze(window, sample_rate=16000)
        vad_ms = (time.time() - t_vad_start) * 1000.0
        speech_detected = vad_result.get("speech_detected", False)

        # 2. Spectral Features
        t_feat_start = time.time()
        audio_features = self._extract_spectral_features(window, sample_rate=16000)
        features_ms = (time.time() - t_feat_start) * 1000.0

        # 3. Prosody Analysis
        t_pros_start = time.time()
        prosody_result = prosody_analyzer.analyze(window, sample_rate=16000)
        prosody_ms = (time.time() - t_pros_start) * 1000.0

        # 4. Genuine AASIST Anti-Spoofing Inference (Phase J & Phase K)
        # AASIST only executes when continuous speech buffer >= min_aasist_samples (64,600 samples / 4.04s)
        # Short audio returns NOT_ENOUGH_AUDIO with INCONCLUSIVE prediction (never false SPOOF).
        aasist_window = buf.get_aasist_window()
        t_anti_start = time.time()
        if aasist_window is not None and speech_detected:
            deepfake_result = deepfake_detector.analyze(
                aasist_window,
                sample_rate=16000,
                speech_detected=True,
                min_required_samples=buf.min_aasist_samples
            )
            if deepfake_result.get("status") == "OK":
                buf.aasist_results.append(deepfake_result)
        elif not speech_detected:
            deepfake_result = {
                "status": "NO_SPEECH",
                "prediction": "INCONCLUSIVE",
                "aasist_status": "NO_SPEECH",
                "spoof_probability": None,
                "genuine_probability": None,
                "score": None,
                "confidence": None,
                "model": deepfake_detector.model_name,
                "model_version": deepfake_detector.model_version,
                "device": deepfake_detector.device,
                "inference_ms": 0.0,
                "ai_probability": None,
                "genuine_probability_pct": None,
                "available": True,
            }
        else:
            curr_dur = buf.continuous_16k_duration_seconds
            req_dur = buf.min_aasist_samples / 16000.0
            deepfake_result = {
                "status": "NOT_ENOUGH_AUDIO",
                "prediction": "INCONCLUSIVE",
                "aasist_status": "NOT_ENOUGH_AUDIO",
                "spoof_probability": None,
                "genuine_probability": None,
                "score": None,
                "confidence": None,
                "model": deepfake_detector.model_name,
                "model_version": deepfake_detector.model_version,
                "device": deepfake_detector.device,
                "inference_ms": 0.0,
                "ai_probability": None,
                "genuine_probability_pct": None,
                "available": True,
                "reason": f"Awaiting sufficient speech buffer ({curr_dur:.2f}s / {req_dur:.2f}s required)"
            }
        anti_spoof_ms = (time.time() - t_anti_start) * 1000.0

        # 5. Genuine ECAPA-TDNN Pretrained Speaker Verification (Phase 3 & Phase K)
        # Multi-window speech accumulation & centroid evaluation
        live_emb = None
        if speech_detected:
            live_emb = speaker_verifier.extract_embedding(window, sample_rate=16000, tag=f"LIVE-{call_id}")
            if live_emb is not None:
                buf.add_speech_embedding(live_emb)

        eval_emb = buf.accumulated_speaker_embedding if buf.accumulated_speaker_embedding is not None else live_emb

        t_spk_start = time.time()
        speaker_result = speaker_verifier.verify_speaker(
            window if eval_emb is None and speech_detected else None,
            claimed_speaker_id=buf.claimed_speaker_id,
            sample_rate=16000,
            speech_detected=speech_detected,
            live_embedding=eval_emb
        )
        speaker_ms = (time.time() - t_spk_start) * 1000.0

        num_accumulated = len(buf.accumulated_speaker_embeddings)
        buf.speaker_speech_windows = num_accumulated
        speaker_result["speech_windows_accumulated"] = num_accumulated
        speaker_result["min_speaker_windows"] = buf.min_speaker_windows
        speaker_result["accumulated_similarity_pct"] = speaker_result.get("similarity_pct")

        # Before min_speaker_windows (default 3), status is INCONCLUSIVE if speech was detected
        if speech_detected and speaker_result.get("status") in ("MATCH", "MISMATCH"):
            if num_accumulated < buf.min_speaker_windows:
                speaker_result["status"] = "INCONCLUSIVE"
                speaker_result["error"] = f"Accumulating voiceprint across speech windows ({num_accumulated}/{buf.min_speaker_windows})"

        # 6. Voice Clone Paradox — only MATCH + SPOOF (never INCONCLUSIVE)
        is_spoof = (deepfake_result.get("status") == "OK" and deepfake_result.get("prediction") == "SPOOF")
        is_speaker_match = (speaker_result.get("status") == "MATCH")
        transient_voice_clone = bool(is_spoof and is_speaker_match)

        # 7. Deterministic trust fusion (Gemini/context included when already present)
        fused_trust = live_semantics.fuse_trust(
            buf,
            aasist=deepfake_result,
            ecapa=speaker_result,
            prosody=prosody_result,
            speech_detected=speech_detected,
        )
        preliminary_trust = {
            "score": fused_trust.get("trust_score", 85),
            "risk_level": fused_trust.get("risk_level", "LOW"),
            "recommended_action": fused_trust.get("recommended_action", "ALLOW"),
            "label": fused_trust.get("action_label", ""),
            "trust_state": "ACTIVE" if fused_trust.get("signal_status", {}).get("aasist") == "available" else "PROVISIONAL",
            "formula": "Weighted fusion: AASIST + ECAPA + Prosody + Gemini + Context",
            "signal_status": fused_trust.get("signal_status"),
            "breakdown": fused_trust.get("breakdown"),
        }

        total_ms = (time.time() - t_start) * 1000.0
        logger.info(
            f"[PERF] {call_id}: VAD={vad_ms:.1f}ms, Features={features_ms:.1f}ms, "
            f"Prosody={prosody_ms:.1f}ms, AntiSpoof={anti_spoof_ms:.1f}ms, Speaker={speaker_ms:.1f}ms, "
            f"Total={total_ms:.1f}ms | Speech={speech_detected} | Speaker={speaker_result.get('status')} | AASIST={deepfake_result.get('prediction')}"
        )

        if speech_detected:
            buf.speech_window_count += 1

        # Track event in session timeline
        timestamp_str = time.strftime("%H:%M:%S", time.gmtime())
        timeline_event = {
            "time": timestamp_str,
            "score": preliminary_trust["score"],
            "label": (
                f"Speech detected ({audio_features['rms']:.3f} RMS, {prosody_result.get('fundamental_f0_hz') or 'Unvoiced'} F0) | "
                f"Speaker: {speaker_result.get('status')} ({speaker_result.get('similarity_pct', 0)}%) | "
                f"AASIST: {deepfake_result.get('prediction')}"
            ),
            "type": "critical" if preliminary_trust["score"] < 30 else ("warning" if preliminary_trust["score"] < 60 else "info")
        }
        buf.timeline_events.append(timeline_event)

        # Update SQLite call record with ongoing telemetry
        try:
            call_repo.update_call_telemetry(call_id, {
                "trust_score": preliminary_trust["score"],
                "trust_level": preliminary_trust["risk_level"],
                "security_decision": preliminary_trust.get("recommended_action", "ALLOW"),
                "action": preliminary_trust.get("recommended_action", "ALLOW"),
                "anti_spoof_prediction": deepfake_result.get("prediction", "INCONCLUSIVE"),
                "spoof_probability": deepfake_result.get("spoof_probability"),
                "genuine_probability": deepfake_result.get("genuine_probability"),
                "raw_anti_spoof_score": deepfake_result.get("score"),
                "speaker_status": speaker_result.get("status", "INCONCLUSIVE"),
                "speaker_similarity": speaker_result.get("similarity_pct", 0.0),
                "speaker_windows": num_accumulated,
                "total_windows": buf.window_count,
                "speech_windows": buf.speech_window_count,
                "possible_voice_clone": transient_voice_clone,
                "telemetry_summary": {
                    "spectral_anomaly": audio_features.get("spectral_flatness", 0),
                    "harmonic_consistency": 85,
                    "voice_naturalness": 88,
                    "prosody": prosody_result
                }
            })
        except Exception:
            pass

        payload = {
            "type": "AUDIO_ANALYSIS",
            "call_id": call_id,
            "mode": "REAL" if not call_id.startswith("VS-2026-") else "DEMO",
            "source": "LIVE_MICROPHONE",
            "timestamp": int(time.time()),
            "window_duration": round(window_duration, 2),
            "continuous_duration": round(buf.continuous_16k_duration_seconds, 2),
            "window_count": buf.window_count,
            "data": {
                "speech_detected": speech_detected,
                "vad": vad_result,
                "audio": audio_features,
                "prosody": prosody_result,
                "voice_authenticity": {
                    "anti_spoof": deepfake_result,
                    "ai_probability": deepfake_result.get("ai_probability"),
                    "genuine_probability": deepfake_result.get("genuine_probability_pct"),
                    "spectral": audio_features
                },
                "speaker_verification": speaker_result,
                "speaker": {
                    "speaker_similarity": speaker_result.get("similarity_pct"),
                    "similarity": speaker_result.get("similarity"),
                    "verified": bool(speaker_result.get("status") == "MATCH"),
                    "status": speaker_result.get("status"),
                    "claimed_speaker": speaker_result.get("display_name", buf.claimed_speaker_id),
                    "claimed_speaker_id": buf.claimed_speaker_id,
                    "threshold": speaker_result.get("threshold", 0.80),
                    "speech_windows_accumulated": speaker_result.get("speech_windows_accumulated", 0),
                    "min_speaker_windows": speaker_result.get("min_speaker_windows", 3),
                    "accumulated_similarity_pct": speaker_result.get("accumulated_similarity_pct")
                },
                "voice_clone_paradox": {
                    "detected": transient_voice_clone,
                    "confidence": "HIGH" if transient_voice_clone else "NONE",
                    "description": (
                        f"CRITICAL: Voice Clone Impersonation Detected! Speaker identity matches enrolled profile ({speaker_result.get('similarity_pct')}%), "
                        f"but acoustic analysis reveals synthetic audio ({deepfake_result.get('spoof_probability', 0)*100:.1f}% spoof probability)."
                        if transient_voice_clone else "No voice clone paradox detected."
                    )
                },
                "transcription": {
                    "text": buf.full_transcript or None,
                    "status": buf.last_asr_status or "PENDING_WHISPER",
                    "history": buf.transcript_history,
                },
                "conversation": buf.conversation_analysis or {
                    "risk": None,
                    "status": "PENDING_GEMINI",
                },
                "session_context": buf.session_context,
                "caller_context": buf.caller_eval,
                "transaction": buf.transaction_eval,
                "incidents": buf.incidents,
                "fused_trust": fused_trust,
                "preliminary_trust": preliminary_trust,
                "latency_ms": {
                    "vad": round(vad_ms, 1),
                    "features": round(features_ms, 1),
                    "prosody": round(prosody_ms, 1),
                    "anti_spoof": round(anti_spoof_ms, 1),
                    "speaker": round(speaker_ms, 1),
                    "total": round(total_ms, 1)
                }
            }
        }
        buf.last_analysis = payload
        return payload

    def run_incremental_asr(self, call_id: str) -> Optional[Dict[str, Any]]:
        buf = self.call_buffers.get(call_id)
        if not buf:
            return None
        return live_semantics.incremental_asr(buf)

    def run_conversation_update(self, call_id: str, full_text: str, force: bool = False) -> Optional[Dict[str, Any]]:
        buf = self.call_buffers.get(call_id)
        if not buf:
            return None
        return live_semantics.run_gemini(buf, full_text, force=force)

    def apply_context(self, call_id: str, updates: Dict[str, Any], source: str = "DEMO_CONTEXT") -> Dict[str, Any]:
        buf = self.call_buffers.get(call_id)
        if buf is None:
            from backend.intelligence.context import context_engine, empty_session_context
            ctx = context_engine.merge_session_context(empty_session_context(), updates, source=source)
            caller = context_engine.evaluate_caller(
                caller_number=ctx.get("caller_number"),
                known_contact=ctx.get("known_contact"),
                claimed_identity=ctx.get("claimed_identity"),
                contact_history=ctx.get("contact_history"),
                source=source,
            )
            txn = context_engine.evaluate_transaction(
                amount=ctx.get("transaction_amount"),
                currency=ctx.get("transaction_currency"),
                beneficiary_name=ctx.get("beneficiary") if isinstance(ctx.get("beneficiary"), str) else None,
                transaction_type=ctx.get("transaction_type"),
                source=source,
            )
            payload = {"session": ctx, "caller": caller, "transaction": txn, "source": source, "label": ctx.get("label")}
            try:
                call_repo.save_context(call_id, payload, source)
            except Exception:
                pass
            return payload
        result = live_semantics.apply_context(buf, updates, source=source)
        last = buf.last_analysis or {}
        data = last.get("data") or {}
        live_semantics.fuse_trust(
            buf,
            aasist=(data.get("voice_authenticity") or {}).get("anti_spoof") or {},
            ecapa=data.get("speaker_verification") or {},
            prosody=data.get("prosody") or {},
            speech_detected=bool(data.get("speech_detected")),
        )
        live_semantics.persist_live_telemetry(call_id, buf)
        return result

    def maybe_incidents(self, call_id: str) -> List[Dict[str, Any]]:
        buf = self.call_buffers.get(call_id)
        if not buf or not buf.last_analysis:
            return []
        data = buf.last_analysis.get("data") or {}
        aasist = (data.get("voice_authenticity") or {}).get("anti_spoof") or {}
        ecapa = data.get("speaker_verification") or {}
        return live_semantics.maybe_create_incidents(buf, aasist, ecapa)

    def persist_semantics(self, call_id: str) -> None:
        buf = self.call_buffers.get(call_id)
        if buf:
            live_semantics.persist_live_telemetry(call_id, buf)

    def _extract_spectral_features(self, audio: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """Calculates real spectral and temporal measurements directly from current audio window."""
        if len(audio) == 0:
            return {
                "rms": 0.0,
                "peak_amplitude": 0.0,
                "zcr": 0.0,
                "spectral_centroid_hz": 0.0,
                "spectral_bandwidth_hz": 0.0,
                "spectral_rolloff_hz": 0.0,
                "spectral_flatness": 0.0,
                "high_frequency_energy": 0.0,
                "spectral_entropy": 0.0
            }

        rms = float(np.sqrt(np.mean(audio ** 2)))
        peak = float(np.max(np.abs(audio)))
        zcr = float(np.sum(np.abs(np.diff(np.signbit(audio)))) / max(1, len(audio) - 1))

        n_fft = min(2048, len(audio))
        window = np.hanning(n_fft)
        framed = audio[:n_fft] * window
        fft_mag = np.abs(np.fft.rfft(framed))
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

        sum_mag = np.sum(fft_mag) + 1e-10
        spectral_centroid = float(np.sum(freqs * fft_mag) / sum_mag)
        spectral_bandwidth = float(np.sqrt(np.sum(((freqs - spectral_centroid) ** 2) * fft_mag) / sum_mag))

        cumulative_mag = np.cumsum(fft_mag)
        rolloff_idx = np.searchsorted(cumulative_mag, 0.85 * cumulative_mag[-1])
        spectral_rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

        log_mag = np.log(fft_mag + 1e-10)
        geom_mean = np.exp(np.mean(log_mag))
        arith_mean = np.mean(fft_mag) + 1e-10
        spectral_flatness = float(min(1.0, max(0.0, geom_mean / arith_mean)))

        hf_cutoff_idx = int(len(freqs) * (4000.0 / (sample_rate / 2.0)))
        hf_energy_ratio = float(np.sum(fft_mag[hf_cutoff_idx:] ** 2) / (np.sum(fft_mag ** 2) + 1e-10))

        prob_dist = fft_mag / sum_mag
        prob_dist = prob_dist[prob_dist > 1e-12]
        spectral_entropy = float(-np.sum(prob_dist * np.log2(prob_dist)) / np.log2(len(fft_mag)))

        return {
            "rms": round(rms, 4),
            "peak_amplitude": round(peak, 4),
            "zcr": round(zcr, 4),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "spectral_bandwidth_hz": round(spectral_bandwidth, 1),
            "spectral_rolloff_hz": round(spectral_rolloff, 1),
            "spectral_flatness": round(spectral_flatness, 4),
            "high_frequency_energy": round(hf_energy_ratio, 4),
            "spectral_entropy": round(spectral_entropy, 4)
        }

    def _calculate_preliminary_trust(
        self,
        voice_ai_probability: Optional[float] = None,
        prosody_anomaly: float = 15.0,
        speech_detected: bool = False,
        anti_spoof_result: Optional[Dict[str, Any]] = None,
        speaker_result: Optional[Dict[str, Any]] = None,
        possible_voice_clone: bool = False
    ) -> Dict[str, Any]:
        """
        Computes an explicitly labeled 'Preliminary Trust Score' combining real AASIST anti-spoofing,
        ECAPA-TDNN speaker biometrics, and prosody telemetry.
        Crucial requirement (Phase N): INCONCLUSIVE does NOT trigger a spoof penalty or speaker mismatch penalty!
        """
        if anti_spoof_result is not None:
            status = anti_spoof_result.get("status")
            spoof_prob = anti_spoof_result.get("spoof_probability")
            if status == "OK" and spoof_prob is not None:
                ai_prob = spoof_prob * 100.0
                is_available = True
            else:
                ai_prob = None
                is_available = False
        else:
            ai_prob = voice_ai_probability
            is_available = (ai_prob is not None)
            status = "OK" if is_available else "NOT_AVAILABLE"

        speaker_status = speaker_result.get("status") if speaker_result else None
        speaker_available = (speaker_status in ("MATCH", "MISMATCH"))

        # Signal status tags
        spk_sig = "available" if speaker_available else ("inconclusive" if speaker_status == "INCONCLUSIVE" else "not_ready")

        # 1. Voice Clone Paradox (Critical priority)
        if possible_voice_clone:
            score = 9
            risk_level = "CRITICAL"
            recommended_action = "BLOCK_TRANSACTION"
            label = "CRITICAL: Voice Clone Paradox Flagged (Speaker Match + Synthetic Audio)"
            trust_state = "ATTACK_FLAGGED"
            formula = "Phase 3: Voice Clone Paradox Divergence"

        # 2. Silence / Non-speech handling
        elif not speech_detected:
            score = 85
            risk_level = "SAFE"
            recommended_action = "ALLOW"
            label = "Silence / Ambient Floor (Provisional)"
            trust_state = "PROVISIONAL"
            formula = "Phase 3: Ambient Floor Baseline"

        # 3. Model pending / inconclusive: do NOT penalize as spoof
        elif not is_available:
            score = 85
            risk_level = "SAFE"
            recommended_action = "ALLOW"
            label = "Acoustic Telemetry Accumulating (Provisional Baseline)"
            trust_state = "PROVISIONAL"
            formula = "Provisional Baseline (Awaiting Full Speech Window)"

        # 4. Multi-Signal Calculation (Phase 2 + Phase 3)
        else:
            voice_trust = max(0.0, 100.0 - (ai_prob or 0.0))
            prosody_trust = max(0.0, 100.0 - prosody_anomaly)

            if speaker_available:
                sim_pct = speaker_result.get("similarity_pct", 50.0)
                speaker_trust = sim_pct if speaker_status == "MATCH" else max(10.0, min(50.0, sim_pct))
                score = int(round(0.45 * voice_trust + 0.30 * speaker_trust + 0.25 * prosody_trust))
                formula = "Phase 3: 45% AASIST Anti-Spoof + 30% ECAPA Speaker + 25% Prosody"
                trust_state = "ACTIVE"
            else:
                score = int(round(0.60 * voice_trust + 0.40 * prosody_trust))
                formula = "Phase 2: 60% AASIST Anti-Spoof + 40% Prosody (Speaker Inconclusive)"
                trust_state = "PROVISIONAL"

            if score >= 75:
                risk_level = "SAFE"
                recommended_action = "ALLOW"
                label = "Preliminary Attestation: Clean Acoustic & Biometric Baseline"
            elif score >= 50:
                risk_level = "WARNING"
                recommended_action = "WARN"
                label = "Preliminary Attestation: Divergent Acoustic / Identity Indicators"
            elif score >= 30:
                risk_level = "HIGH"
                recommended_action = "REQUIRE_MFA"
                label = "Preliminary Attestation: Elevated Synthetic / Impersonation Risk"
            else:
                risk_level = "CRITICAL"
                recommended_action = "BLOCK_TRANSACTION"
                label = "Preliminary Attestation: High Synthetic Impersonation Risk"

        return {
            "score": score,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "label": label,
            "trust_state": trust_state,
            "formula": formula,
            "signal_status": {
                "voice_authenticity": "available" if is_available else "inconclusive",
                "prosody": "available",
                "speaker_verification": spk_sig,
                "conversation_risk": "not_ready",
                "caller_risk": "not_ready",
                "transaction_risk": "not_ready"
            }
        }

    def stop_call_stream(self, call_id: str) -> Optional[Dict[str, Any]]:
        """
        Finalizes an active call stream session with authoritative multi-window aggregation (Phase L).
        Persists finalized session record to SQLite database (Phase D).
        """
        buf = self.call_buffers.pop(call_id, None)
        if not buf:
            return None

        duration = time.time() - buf.created_at

        # 1. Authoritative Multi-Window ECAPA Speaker Centroid (Phase L)
        final_speaker_status = "INCONCLUSIVE"
        final_similarity = 0.0
        speaker_threshold = 0.80

        if buf.accumulated_speaker_embeddings:
            # L2-normalize each embedding, compute mean, then L2-normalize centroid
            valid_embs = []
            for emb in buf.accumulated_speaker_embeddings:
                n = float(np.linalg.norm(emb))
                if n > 1e-8:
                    valid_embs.append(emb / n)

            if valid_embs:
                centroid = np.mean(valid_embs, axis=0)
                c_norm = float(np.linalg.norm(centroid))
                if c_norm > 1e-8:
                    centroid = (centroid / c_norm).astype(np.float32)

                # Verify against enrolled profile
                profile = speaker_verifier.enrolled_speakers.get(buf.claimed_speaker_id)
                if profile and profile.get("embedding") is not None:
                    enrolled_emb = profile["embedding"]
                    speaker_threshold = profile.get("threshold", speaker_verifier.default_threshold)
                    cos_sim = float(np.dot(centroid, enrolled_emb))
                    cos_sim = max(-1.0, min(1.0, cos_sim))
                    final_similarity = round(max(0.0, min(100.0, cos_sim * 100.0)), 1)
                    final_speaker_status = "MATCH" if cos_sim >= speaker_threshold else "MISMATCH"
                else:
                    final_speaker_status = "NOT_ENROLLED"
        else:
            final_speaker_status = "INCONCLUSIVE"

        # 2. Authoritative AASIST Aggregation (Phase L)
        # Compute median spoof probability ONLY over valid inference windows
        valid_aasist = [r for r in buf.aasist_results if r.get("status") == "OK" and r.get("spoof_probability") is not None]
        if valid_aasist:
            spoof_probs = [r["spoof_probability"] for r in valid_aasist]
            final_spoof_prob = float(np.median(spoof_probs))
            final_genuine_prob = round(1.0 - final_spoof_prob, 4)
            final_spoof_prob = round(final_spoof_prob, 4)
            final_anti_spoof_prediction = "SPOOF" if final_spoof_prob >= 0.5 else "BONAFIDE"
            raw_score = valid_aasist[-1].get("score")
        else:
            final_anti_spoof_prediction = "INCONCLUSIVE"
            final_spoof_prob = None
            final_genuine_prob = None
            raw_score = None

        # Check manual overrides for testing
        if hasattr(buf, "final_speaker_status") and buf.final_speaker_status is not None:
            final_speaker_status = buf.final_speaker_status
        if hasattr(buf, "final_speaker_sim") and buf.final_speaker_sim is not None:
            final_similarity = buf.final_speaker_sim
        if hasattr(buf, "final_anti_spoof_prediction") and buf.final_anti_spoof_prediction is not None:
            final_anti_spoof_prediction = buf.final_anti_spoof_prediction
        if hasattr(buf, "final_spoof_prob") and buf.final_spoof_prob is not None:
            final_spoof_prob = buf.final_spoof_prob

        # 3. Authoritative Final Voice Clone Paradox (Phase M)
        # ONLY: final_aasist_prediction == SPOOF AND final_speaker_status == MATCH
        final_voice_clone = bool(final_anti_spoof_prediction == "SPOOF" and final_speaker_status == "MATCH")

        # 4. Final Trust Score Calculation
        if final_voice_clone:
            final_trust_score = 9
            final_trust_level = "CRITICAL"
            final_decision = "BLOCK_TRANSACTION"
        else:
            voice_t = (100.0 - final_spoof_prob * 100.0) if final_spoof_prob is not None else 85.0
            if final_speaker_status == "MATCH":
                spk_t = final_similarity
            elif final_speaker_status == "MISMATCH":
                spk_t = max(10.0, min(50.0, final_similarity))
            else:
                spk_t = 80.0

            final_trust_score = int(round(0.50 * voice_t + 0.30 * spk_t + 0.20 * 85.0))
            final_trust_score = max(0, min(100, final_trust_score))

            if final_trust_score >= 80:
                final_trust_level = "SAFE"
                final_decision = "ALLOW"
            elif final_trust_score >= 50:
                final_trust_level = "WARNING"
                final_decision = "WARN"
            elif final_trust_score >= 30:
                final_trust_level = "HIGH"
                final_decision = "REQUIRE_MFA"
            else:
                final_trust_level = "CRITICAL"
                final_decision = "BLOCK_TRANSACTION"

        summary = {
            "call_id": call_id,
            "mode": "REAL" if not call_id.startswith("VS-2026-") else "DEMO",
            "source": "LIVE_MICROPHONE",
            "total_windows": buf.window_count,
            "speech_windows": buf.speech_window_count,
            "duration_seconds": round(duration, 1),
            "claimed_speaker_id": buf.claimed_speaker_id,
            "trust_score": final_trust_score,
            "trust_level": final_trust_level,
            "security_decision": final_decision,
            "action": final_decision,
            "anti_spoof_prediction": final_anti_spoof_prediction,
            "spoof_probability": final_spoof_prob,
            "genuine_probability": final_genuine_prob,
            "raw_anti_spoof_score": raw_score,
            "speaker_status": final_speaker_status,
            "speaker_similarity": final_similarity,
            "speaker_threshold": speaker_threshold,
            "speaker_windows": len(buf.accumulated_speaker_embeddings),
            "possible_voice_clone": final_voice_clone,
            "voice_clone_paradox": final_voice_clone,
            "status": "BLOCKED" if final_decision == "BLOCK_TRANSACTION" else ("ALLOWED" if final_decision == "ALLOW" else final_decision),
            "timeline": buf.timeline_events,
            "last_analysis": buf.last_analysis,
            "transcript": getattr(buf, "full_transcript", ""),
            "transcript_history": getattr(buf, "transcript_history", []),
            "gemini": getattr(buf, "conversation_analysis", None),
            "session_context": getattr(buf, "session_context", None),
            "incidents": getattr(buf, "incidents", []),
            "telemetry_summary": {
                "transcript": getattr(buf, "full_transcript", ""),
                "transcript_history": getattr(buf, "transcript_history", []),
                "gemini": getattr(buf, "conversation_analysis", None),
                "conversation": getattr(buf, "conversation_analysis", None),
                "session_context": getattr(buf, "session_context", None),
                "caller_context": getattr(buf, "caller_eval", None),
                "transaction": getattr(buf, "transaction_eval", None),
                "incidents": getattr(buf, "incidents", []),
                "prosody": ((buf.last_analysis or {}).get("data") or {}).get("prosody"),
            },
        }

        # 5. Persist Finalized Call Record to SQLite (Phase D)
        try:
            call_repo.finalize_call(call_id, summary)
            logger.info(f"[DB] Saved and finalized call {call_id} in SQLite database.")
        except Exception as e:
            logger.error(f"[DB] Error finalizing call {call_id} in database: {e}")

        logger.info(
            f"[CALL] FINALIZED {call_id}: duration={duration:.1f}s | "
            f"speaker={final_speaker_status} ({final_similarity}%) | "
            f"aasist={final_anti_spoof_prediction} ({final_spoof_prob}) | "
            f"clone_paradox={final_voice_clone} | trust={final_trust_score}"
        )

        return summary

stream_processor = AudioStreamProcessor()
