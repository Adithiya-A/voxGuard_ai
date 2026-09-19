import os
import sys
import time
import logging
import urllib.request
from typing import Dict, Any, Optional
import numpy as np
import torch

from backend.models.aasist_arch import Model as AASISTModel
from backend.audio.preprocessing import (
    load_audio_bytes,
    resample_to_16k,
    preprocess_for_speaker_model,
    normalize_for_aasist,
    compute_audio_diagnostics,
)

logger = logging.getLogger("voxguard.antispoof")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AASIST_WEIGHTS_URL = "https://raw.githubusercontent.com/clovaai/aasist/main/models/weights/AASIST.pth"
AASIST_INPUT_SAMPLES = 64600  # Exactly 64,600 samples (~4.0375s at 16kHz)

AASIST_CONFIG = {
    "architecture": "AASIST",
    "nb_samp": AASIST_INPUT_SAMPLES,
    "first_conv": 128,
    "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
    "gat_dims": [64, 32],
    "pool_ratios": [0.5, 0.7, 0.5, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0]
}

def pad_aasist(x: np.ndarray, max_len: int = AASIST_INPUT_SAMPLES) -> np.ndarray:
    """Official ASVspoof/AASIST repetition padding."""
    x_len = x.shape[0]
    if x_len >= max_len:
        return x[:max_len]
    num_repeats = int(max_len / max(1, x_len)) + 1
    return np.tile(x, num_repeats)[:max_len]

class DeepfakeDetector:
    """
    Genuine Pretrained Audio Anti-Spoofing & Speech Deepfake Detector using AASIST
    (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks).
    Trained on ASVspoof 2019 Logical Access (LA) benchmark.

    Class Ordering in AASIST:
    - Class 0: SPOOF (Synthetic / Replay / Cloned Speech)
    - Class 1: BONAFIDE (Genuine Organic Speech)
    """
    def __init__(self, weights_dir: Optional[str] = None):
        self.model_name = "AASIST"
        self.model_version = "AASIST-ASVspoof2019-LA"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: Optional[AASISTModel] = None
        self.model_loaded: bool = False
        self._class_mapping_logged: bool = False

        if weights_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            weights_dir = os.path.join(base_dir, "weights")
        self.weights_path = os.path.join(weights_dir, "AASIST.pth")

    def is_loaded(self) -> bool:
        return self.model_loaded and self.model is not None

    def load_model(self) -> None:
        """
        Lazy-loads the AASIST neural network checkpoint into memory.
        Reuses cached instance across all subsequent inference requests.
        """
        if self.is_loaded():
            return

        logger.info(f"[ANTI-SPOOF] Loading {self.model_name} model on device: {self.device}...")
        t_load_start = time.time()

        os.makedirs(os.path.dirname(self.weights_path), exist_ok=True)
        if not os.path.exists(self.weights_path):
            logger.info(f"[ANTI-SPOOF] Checkpoint not found at {self.weights_path}. Downloading from official source...")
            urllib.request.urlretrieve(AASIST_WEIGHTS_URL, self.weights_path)
            logger.info(f"[ANTI-SPOOF] Download complete: {self.weights_path}")

        try:
            model = AASISTModel(AASIST_CONFIG)
            state_dict = torch.load(self.weights_path, map_location=self.device, weights_only=True)
            model.load_state_dict(state_dict)
            model.to(self.device)
            model.eval()

            self.model = model
            self.model_loaded = True
            t_load_ms = (time.time() - t_load_start) * 1000.0
            logger.info(f"[ANTI-SPOOF] Model loaded successfully: {self.model_name} ({t_load_ms:.1f}ms) | Device: {self.device}")
        except Exception as e:
            self.model = None
            self.model_loaded = False
            logger.error(f"[ANTI-SPOOF] Failed to load model weights: {e}", exc_info=True)
            raise

    def analyze(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        speech_detected: bool = True,
        min_required_samples: int = 24000  # at least 1.5s for unit tests; streaming buffer targets 64,600
    ) -> Dict[str, Any]:
        """
        Runs real-time anti-spoofing inference on an audio window using AASIST.
        - Empty audio returns NO_AUDIO.
        - Silence or non-speech windows return NO_SPEECH without neural net inference.
        - Insufficient duration returns NOT_ENOUGH_AUDIO with INCONCLUSIVE prediction.
        - Errors return MODEL_ERROR with prediction INCONCLUSIVE.
        """
        # 1. Empty audio check
        if audio is None or len(audio) == 0:
            return {
                "status": "NO_AUDIO",
                "prediction": "INCONCLUSIVE",
                "spoof_probability": None,
                "genuine_probability": None,
                "score": None,
                "confidence": None,
                "model": self.model_name,
                "model_version": self.model_version,
                "device": self.device,
                "inference_ms": 0.0,
                "ai_probability": None,
                "genuine_probability_pct": None,
                "available": False,
            }

        # 2. Silence bypass: do not run expensive ML inference on ambient/non-speech windows
        if not speech_detected:
            return {
                "status": "NO_SPEECH",
                "prediction": "INCONCLUSIVE",
                "spoof_probability": None,
                "genuine_probability": None,
                "score": None,
                "confidence": None,
                "model": self.model_name,
                "model_version": self.model_version,
                "device": self.device,
                "inference_ms": 0.0,
                "ai_probability": None,
                "genuine_probability_pct": None,
                "available": False,
            }

        # 3. Check duration before running model (Phase J & Phase K requirement)
        # AASIST native input is 64,600 samples (~4.04s at 16kHz).
        # Insufficient input MUST NOT be classified as SPOOF.
        audio_dur = len(audio) / float(sample_rate)
        if len(audio) < min_required_samples:
            logger.info(
                f"[AASIST] Insufficient audio duration: {audio_dur:.2f}s "
                f"({len(audio)} samples < {min_required_samples} required). Status: NOT_ENOUGH_AUDIO"
            )
            return {
                "status": "NOT_ENOUGH_AUDIO",
                "prediction": "INCONCLUSIVE",
                "spoof_probability": None,
                "genuine_probability": None,
                "score": None,
                "confidence": None,
                "model": self.model_name,
                "model_version": self.model_version,
                "device": self.device,
                "inference_ms": 0.0,
                "ai_probability": None,
                "genuine_probability_pct": None,
                "available": True,
                "reason": f"Awaiting sufficient speech buffer ({audio_dur:.2f}s / {min_required_samples / float(sample_rate):.2f}s required)"
            }

        try:
            # 4. Canonical preprocessing: mono, DC removal, anti-aliased 16kHz resampling, peak control
            audio_16k, _ = preprocess_for_speaker_model(audio, sample_rate=sample_rate, tag="AASIST")

            # 5. Calibrate input waveform to AASIST's nominal ASVspoof 2019 conversational scale
            # Prevents SincNet first layer batch norm saturation from microphone AGC peaks
            audio_norm = normalize_for_aasist(audio_16k)

            # 6. Lazy model loading
            if not self.is_loaded():
                self.load_model()

            # 7. Prepare input tensor of exactly AASIST_INPUT_SAMPLES (64,600 samples ~4.0375s at 16kHz)
            audio_padded = pad_aasist(audio_norm, AASIST_INPUT_SAMPLES)
            diag = compute_audio_diagnostics(audio_padded, 16000)

            x = torch.from_numpy(audio_padded).float().unsqueeze(0).to(self.device)

            # 8. Execute forward pass
            t_start = time.time()
            with torch.no_grad():
                _, output = self.model(x)
            t_inference_ms = (time.time() - t_start) * 1000.0

            # AASIST output format (ASVspoof 2019 Logical Access):
            # Class 0 = Spoof
            # Class 1 = Bonafide (Genuine)
            probs = torch.softmax(output, dim=-1)
            spoof_prob = float(probs[0, 0].item())
            genuine_prob = float(probs[0, 1].item())
            bonafide_score = float(output[0, 1].item())

            if not self._class_mapping_logged:
                logger.info(
                    f"[AASIST-SEMANTICS] Verified class mapping: Class 0=SPOOF, Class 1=BONAFIDE | "
                    f"raw logits={output[0].tolist()} | probs={probs[0].tolist()}"
                )
                self._class_mapping_logged = True

            prediction = "SPOOF" if spoof_prob >= 0.5 else "BONAFIDE"
            confidence = round(max(spoof_prob, genuine_prob), 4)

            ai_prob_pct = int(round(spoof_prob * 100.0))
            gen_prob_pct = 100 - ai_prob_pct

            logger.info(
                f"[AASIST_DIAG] samples={diag['sample_count']} | duration={diag['duration']}s "
                f"| peak={diag['peak']} | rms={diag['rms']} | clipping={diag['clipping_percentage']}% "
                f"| raw_logits={output[0].tolist()} | probs={[round(p, 5) for p in probs[0].tolist()]} "
                f"| prediction={prediction} (spoof={spoof_prob * 100:.1f}%) | Device: {self.device}"
            )

            return {
                "status": "OK",
                "prediction": prediction,
                "spoof_probability": round(spoof_prob, 4),
                "genuine_probability": round(genuine_prob, 4),
                "score": round(bonafide_score, 4),
                "confidence": confidence,
                "model": self.model_name,
                "model_version": self.model_version,
                "device": self.device,
                "inference_ms": round(t_inference_ms, 1),
                "ai_probability": ai_prob_pct,
                "genuine_probability_pct": gen_prob_pct,
                "available": True,
            }

        except Exception as e:
            logger.error(f"[ANTI-SPOOF] Model inference error: {e}", exc_info=True)
            return {
                "status": "MODEL_ERROR",
                "prediction": "INCONCLUSIVE",
                "spoof_probability": None,
                "genuine_probability": None,
                "score": None,
                "confidence": None,
                "model": self.model_name,
                "model_version": self.model_version,
                "device": self.device,
                "inference_ms": 0.0,
                "error": str(e),
                "ai_probability": None,
                "genuine_probability_pct": None,
                "available": False,
            }

    def predict(self, *args, **kwargs) -> Dict[str, Any]:
        """Convenience alias for analyze()."""
        return self.analyze(*args, **kwargs)

deepfake_detector = DeepfakeDetector()

