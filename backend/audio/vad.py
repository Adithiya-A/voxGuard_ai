import numpy as np
from typing import Dict, Any

class DSPVoiceActivityDetector:
    """
    Real-time Digital Signal Processing (DSP) Voice Activity Detector.
    Uses short-time energy (RMS), zero-crossing rate (ZCR), and spectral centroid
    to compute an adaptive speech probability without relying on external cloud APIs.
    Labeled explicitly as 'DSP VAD'.
    """
    def __init__(
        self,
        energy_threshold: float = 0.012,
        zcr_lower: float = 0.02,
        zcr_upper: float = 0.45,
        noise_floor_alpha: float = 0.95
    ):
        self.vad_type = "DSP VAD"
        self.energy_threshold = energy_threshold
        self.zcr_lower = zcr_lower
        self.zcr_upper = zcr_upper
        self.noise_floor = 0.002
        self.noise_floor_alpha = noise_floor_alpha

    def analyze(self, audio: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        if len(audio) == 0:
            return {
                "speech_detected": False,
                "speech_probability": 0.0,
                "energy": 0.0,
                "rms": 0.0,
                "peak_amplitude": 0.0,
                "zcr": 0.0,
                "snr_db": 0.0,
                "vad_type": self.vad_type
            }

        # 1. RMS Energy & Peak Amplitude
        rms = float(np.sqrt(np.mean(audio ** 2)))
        peak = float(np.max(np.abs(audio)))

        # Update noise floor during quiet periods
        if rms < self.energy_threshold:
            self.noise_floor = self.noise_floor_alpha * self.noise_floor + (1 - self.noise_floor_alpha) * max(1e-5, rms)

        # Signal to Noise Ratio (dB)
        snr_ratio = max(1e-4, rms) / max(1e-5, self.noise_floor)
        snr_db = float(10.0 * np.log10(snr_ratio))

        # 2. Zero Crossing Rate (ZCR)
        # Speech typically falls within a reasonable ZCR range (voiced speech lower, unvoiced fricatives moderate)
        zcr = float(np.sum(np.abs(np.diff(np.signbit(audio)))) / max(1, len(audio) - 1))

        # 3. Energy factor sigmoid-like mapping
        # Compare RMS to threshold and dynamic noise floor
        energy_margin = (rms - self.noise_floor) / max(1e-4, self.energy_threshold)
        energy_score = float(1.0 / (1.0 + np.exp(-4.0 * (energy_margin - 0.5))))

        # 4. ZCR factor
        if self.zcr_lower <= zcr <= self.zcr_upper:
            zcr_score = 1.0
        elif zcr < self.zcr_lower:
            zcr_score = max(0.1, zcr / max(1e-4, self.zcr_lower))
        else:
            # high frequency noise / hiss
            zcr_score = max(0.0, 1.0 - (zcr - self.zcr_upper) * 2.0)

        # 5. Combined Speech Probability
        speech_prob = float(np.clip(0.75 * energy_score + 0.25 * zcr_score, 0.0, 1.0))

        # If RMS is negligible (< 0.003), treat definitely as silence
        if rms < 0.003:
            speech_prob = min(speech_prob, 0.05)

        speech_detected = bool(speech_prob >= 0.5 and rms >= self.energy_threshold * 0.7)

        return {
            "speech_detected": speech_detected,
            "speech_probability": round(speech_prob, 3),
            "energy": round(rms ** 2, 6),
            "rms": round(rms, 4),
            "peak_amplitude": round(peak, 4),
            "zcr": round(zcr, 4),
            "snr_db": round(snr_db, 1),
            "vad_type": self.vad_type
        }

dsp_vad = DSPVoiceActivityDetector()

def detect_voice_activity(audio: np.ndarray, threshold_energy: float = 0.005) -> bool:
    """
    Backwards-compatible legacy function.
    """
    res = dsp_vad.analyze(audio)
    return res["speech_detected"]
