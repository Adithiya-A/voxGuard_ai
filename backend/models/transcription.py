import os
import time
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from backend.config import settings

logger = logging.getLogger("voxguard.whisper")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ALLOWED_WHISPER_MODELS = ("tiny", "base", "small")


class TranscriptionService:
    """
    Real Whisper-compatible ASR using faster-whisper.
    Lazy-loaded singleton. Never returns scripted demo transcripts.
    """

    def __init__(self):
        requested = (os.getenv("WHISPER_MODEL") or settings.WHISPER_MODEL or "base").strip().lower()
        self.model_size = requested if requested in ALLOWED_WHISPER_MODELS else "base"
        self.engine = "faster-whisper"
        self.model_name = f"faster-whisper-{self.model_size}"
        self._model = None
        self._load_error: Optional[str] = None
        self.device = "cpu"
        self.compute_type = "int8"

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_state(self) -> Dict[str, Any]:
        return {
            "available": self._load_error is None,
            "loaded": self.is_loaded(),
            "model": self.model_name,
            "engine": self.engine,
            "device": self.device,
            "error": self._load_error,
        }

    def load_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from faster_whisper import WhisperModel

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.compute_type = "float16" if self.device == "cuda" else "int8"
            t0 = time.time()
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._load_error = None
            logger.info(
                f"[WHISPER] Loaded {self.model_name} on {self.device} "
                f"({(time.time() - t0) * 1000:.1f}ms, compute={self.compute_type})"
            )
        except Exception as e:
            self._model = None
            self._load_error = str(e)
            logger.error(f"[WHISPER] Unavailable: {e}")
            raise

    def transcribe_audio(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        call_id: str = "LIVE",
    ) -> Dict[str, Any]:
        duration = float(len(audio) / float(sample_rate)) if audio is not None and len(audio) > 0 else 0.0
        base = {
            "text": "",
            "language": None,
            "segments": [],
            "duration": round(duration, 3),
            "inference_ms": 0.0,
            "model": self.engine,
            "model_size": self.model_size,
            "device": self.device,
            "available": False,
        }

        if audio is None or len(audio) == 0:
            return {**base, "status": "NO_AUDIO", "prediction": "NO_AUDIO"}

        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak > 1.0:
            audio = audio / (peak + 1e-8)
        rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0

        logger.info(
            f"[WHISPER_INPUT] call_id={call_id} sr={sample_rate} samples={len(audio)} "
            f"duration={duration:.3f}s rms={rms:.4f} peak={peak:.4f}"
        )

        if rms < 1e-4 or duration < 0.25:
            return {
                **base,
                "status": "NO_SPEECH",
                "available": True,
                "text": "",
            }

        try:
            if not self.is_loaded():
                self.load_model()
        except Exception as e:
            return {
                **base,
                "status": "WHISPER_UNAVAILABLE",
                "available": False,
                "error": str(e),
            }

        try:
            t0 = time.time()
            segments_iter, info = self._model.transcribe(
                audio,
                language=None,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                beam_size=1,
            )
            segments: List[Dict[str, Any]] = []
            texts: List[str] = []
            for seg in segments_iter:
                piece = (seg.text or "").strip()
                if not piece:
                    continue
                texts.append(piece)
                logger.info(f"[WHISPER_RESULT] start={seg.start:.2f} end={seg.end:.2f} text=\"{piece}\"")
                segments.append({
                    "start": round(float(seg.start), 2),
                    "end": round(float(seg.end), 2),
                    "text": piece,
                })
            inference_ms = (time.time() - t0) * 1000.0
            full_text = " ".join(texts).strip()
            language = getattr(info, "language", None)
            return {
                "text": full_text,
                "language": language,
                "segments": segments,
                "duration": round(duration, 3),
                "inference_ms": round(inference_ms, 1),
                "model": self.engine,
                "model_size": self.model_size,
                "device": self.device,
                "available": True,
                "status": "OK" if full_text else "NO_SPEECH",
            }
        except Exception as e:
            logger.error(f"[WHISPER] Inference error: {e}", exc_info=True)
            return {
                **base,
                "status": "MODEL_ERROR",
                "available": False,
                "error": str(e),
            }

    def transcribe_chunk(self, chunk_index: int, scenario: str = "clone") -> Dict[str, Any]:
        """
        Demo-only timeline helper. LIVE microphone path must never call this.
        """
        return {
            "current_line": None,
            "transcript_history": [],
            "full_text": "",
            "model_version": self.model_name,
            "status": "DEMO_ONLY",
            "note": "Scripted demo transcripts are isolated from LIVE Whisper ASR.",
            "chunk_index": chunk_index,
            "scenario": scenario,
        }


transcription_service = TranscriptionService()
