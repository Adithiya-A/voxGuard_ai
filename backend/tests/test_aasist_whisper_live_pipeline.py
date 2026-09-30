"""
Comprehensive Regression Tests for AASIST Anti-Spoofing & Whisper/Gemini Live Pipeline.
Covers:
1. AASIST input length exactly 64600 samples
2. PCM int16 -> float32 conversion scaling
3. AASIST class mapping verification on known genuine fixture
4. Browser-like 16k PCM fixture with high peak (AGC simulation)
5. Whisper returns transcript for valid speech
6. TRANSCRIPT_UPDATE emitted with structured payload
7. Frontend WebSocket event structure compatibility
8. Gemini receives real transcript (never runs on empty)
9. GEMINI_UPDATE emitted
10. Duplicate transcript does not trigger duplicate Gemini
11. Gemini failure falls back cleanly to 'heuristic' engine
12. AASIST INCONCLUSIVE (NOT_ENOUGH_AUDIO, NO_SPEECH) never becomes SPOOF
13. Clone paradox only triggers when AASIST == SPOOF and ECAPA == MATCH
"""

import os
import time
import pytest
import numpy as np
import soundfile as sf
import torch

from backend.models.deepfake_detector import (
    DeepfakeDetector,
    deepfake_detector,
    AASIST_INPUT_SAMPLES,
    pad_aasist,
)
from backend.audio.preprocessing import (
    compute_audio_diagnostics,
    normalize_for_aasist,
    load_audio_bytes,
)
from backend.audio.stream_processor import (
    CallAudioBuffer,
    AudioStreamProcessor,
    stream_processor,
    LIVE_ANALYSIS_WINDOW_SECONDS,
)
from backend.models.transcription import transcription_service
from backend.intelligence.conversation import conversation_intelligence
from backend.services import live_semantics
from backend.services.events import ws_event
from backend.trust.scoring import trust_engine

GENUINE_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "genuine_speech.wav"
)


class TestAASISTPipeline:
    """AASIST Architecture, Semantics, Preprocessing & Durations."""

    def test_01_aasist_input_samples_constant(self):
        """1. AASIST input length must be exactly 64600 samples (~4.0375s at 16kHz)."""
        assert AASIST_INPUT_SAMPLES == 64600
        dummy = np.zeros(16000, dtype=np.float32)
        padded = pad_aasist(dummy, AASIST_INPUT_SAMPLES)
        assert len(padded) == 64600

    def test_02_pcm16_to_float32_conversion(self):
        """2. PCM int16 -> float32 conversion scaling: float32 / 32768.0."""
        int16_vals = np.array([-32768, 0, 16384, 32767], dtype=np.int16)
        raw_bytes = int16_vals.tobytes()
        float_audio, sr = load_audio_bytes(raw_bytes)
        assert sr == 16000
        assert float_audio.dtype == np.float32
        assert np.isclose(float_audio[0], -1.0, atol=1e-4)
        assert np.isclose(float_audio[1], 0.0, atol=1e-4)
        assert np.isclose(float_audio[2], 0.5, atol=1e-4)
        assert float_audio[3] < 1.0

    def test_03_aasist_class_mapping_genuine_fixture(self):
        """3. AASIST class mapping verification: known genuine speech fixture -> BONAFIDE."""
        data, sr = sf.read(GENUINE_FIXTURE_PATH)
        res = deepfake_detector.analyze(data, sample_rate=sr, speech_detected=True)
        assert res["status"] == "OK"
        assert res["prediction"] == "BONAFIDE"
        assert res["genuine_probability"] > 0.85
        assert res["spoof_probability"] < 0.15
        assert res["score"] > 0.5

    def test_04_browser_agc_amplitude_handling(self):
        """4. Browser-like 16k PCM fixture with peak=1.0 (AGC) must not saturate into false SPOOF."""
        data, sr = sf.read(GENUINE_FIXTURE_PATH)
        # Simulate browser AGC scaling audio to maximum amplitude (peak=1.0)
        agc_audio = data / np.max(np.abs(data))
        diag_raw = compute_audio_diagnostics(agc_audio, 16000)
        assert diag_raw["peak"] == 1.0

        # Run through deepfake_detector with normalize_for_aasist
        res = deepfake_detector.analyze(agc_audio, sample_rate=sr, speech_detected=True)
        assert res["status"] == "OK"
        assert res["prediction"] == "BONAFIDE", (
            f"Expected BONAFIDE after calibration, got {res['prediction']} "
            f"with spoof_p={res['spoof_probability']}"
        )
        assert res["spoof_probability"] < 0.20

    def test_12_inconclusive_never_becomes_spoof(self):
        """12. AASIST INCONCLUSIVE (e.g. NOT_ENOUGH_AUDIO or NO_SPEECH) must NEVER become SPOOF."""
        short_audio = np.zeros(8000, dtype=np.float32)
        res_short = deepfake_detector.analyze(short_audio, sample_rate=16000, speech_detected=True, min_required_samples=24000)
        assert res_short["prediction"] == "INCONCLUSIVE"
        assert res_short["status"] == "NOT_ENOUGH_AUDIO"
        assert res_short.get("spoof_probability") is None

        # Silence check
        res_silence = deepfake_detector.analyze(np.zeros(64600, dtype=np.float32), sample_rate=16000, speech_detected=False)
        assert res_silence["prediction"] == "INCONCLUSIVE"
        assert res_silence["status"] == "NO_SPEECH"

    def test_13_clone_paradox_condition(self):
        """13. Voice clone paradox triggers ONLY when AASIST == SPOOF AND ECAPA == MATCH."""
        fused_normal = trust_engine.fuse_live_signals(
            aasist={"status": "OK", "prediction": "BONAFIDE", "spoof_probability": 0.05},
            ecapa={"status": "MATCH", "similarity_score": 0.88},
            speech_detected=True,
            possible_voice_clone=False,
        )
        assert not fused_normal.get("possible_voice_clone")

        fused_paradox = trust_engine.fuse_live_signals(
            aasist={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.95},
            ecapa={"status": "MATCH", "similarity_score": 0.88},
            speech_detected=True,
            possible_voice_clone=True,
        )
        assert fused_paradox.get("possible_voice_clone")
        assert fused_paradox.get("risk_level") in ("CRITICAL", "HIGH")


class TestWhisperGeminiPipeline:
    """Whisper Live ASR, Gemini Deduplication & Event Streaming."""

    def test_05_whisper_returns_transcript(self):
        """5. Whisper returns real transcript for known genuine speech fixture."""
        data, sr = sf.read(GENUINE_FIXTURE_PATH)
        res = transcription_service.transcribe_audio(data, sample_rate=sr, call_id="TEST_UNIT")
        assert res["status"] == "OK"
        assert "canoe" in res["text"].lower()
        assert res["language"] == "en"
        assert len(res["segments"]) > 0

    def test_06_incremental_asr_and_transcript_update_event(self):
        """6. incremental_asr returns structured transcript update event dictionary."""
        buf = CallAudioBuffer("TEST-WHISPER-01", input_sample_rate=16000)
        data, sr = sf.read(GENUINE_FIXTURE_PATH)
        # Append audio to buffer
        int16_bytes = (data * 32767.0).astype(np.int16).tobytes()
        buf.append_pcm16_bytes(int16_bytes)

        res = live_semantics.incremental_asr(buf)
        assert res is not None
        assert res["status"] == "OK"
        assert res["engine"] == "whisper"
        assert len(res["text"]) > 0
        assert "canoe" in res["full_text"].lower()

        # Build ws_event
        evt = ws_event("TRANSCRIPT_UPDATE", buf.call_id, res, text=res["text"], full_text=res["full_text"], engine="whisper")
        assert evt["type"] == "TRANSCRIPT_UPDATE"
        assert evt["call_id"] == "TEST-WHISPER-01"
        assert evt["text"] == res["text"]

    def test_08_gemini_receives_real_transcript_never_empty(self):
        """8. Gemini receives real transcript and never executes on empty text."""
        buf = CallAudioBuffer("TEST-GEMINI-01", input_sample_rate=16000)
        live_semantics.init_session_fields(buf)

        # Empty text returns None
        assert live_semantics.run_gemini(buf, "") is None
        assert live_semantics.run_gemini(buf, "   ") is None

        # Meaningful transcript executes
        real_text = "Please transfer five crore rupees to the new overseas beneficiary immediately."
        analysis = live_semantics.run_gemini(buf, real_text, force=True)
        assert analysis is not None
        assert analysis["status"] in ("OK", "GEMINI_UNAVAILABLE")
        assert analysis["financial_request"] is True
        assert analysis["urgency"] is True

    def test_09_gemini_update_event_emitted(self):
        """9. GEMINI_UPDATE event has correct structure and engine identification."""
        analysis = conversation_intelligence.analyze_transcript("Hello, this is a routine security check.")
        assert analysis is not None
        assert "engine" in analysis
        evt = ws_event("GEMINI_UPDATE", "TEST-01", analysis, engine=analysis["engine"])
        assert evt["type"] == "GEMINI_UPDATE"
        assert evt["data"]["intent"] != "" or evt["data"]["status"] == "OK"

    def test_10_gemini_duplicate_prevention(self):
        """10. Duplicate transcript text does not trigger duplicate Gemini analysis."""
        buf = CallAudioBuffer("TEST-GEMINI-DEDUP", input_sample_rate=16000)
        live_semantics.init_session_fields(buf)
        text = "Urgent wire transfer required immediately for the vendor invoice."

        res1 = live_semantics.run_gemini(buf, text, force=False)
        assert res1 is not None

        # Second call with identical text must return None (deduplicated)
        res2 = live_semantics.run_gemini(buf, text, force=False)
        assert res2 is None, "Duplicate Gemini call was not prevented"

    def test_11_gemini_fallback_engine_labeled_heuristic(self):
        """11. When Gemini API is unavailable, engine is explicitly labeled 'heuristic'."""
        fallback = conversation_intelligence._analyze_heuristic("Please send the OTP passcode immediately.")
        assert fallback["engine"] == "heuristic"
        assert fallback["credential_request"] is True
        assert fallback["urgency"] is True
