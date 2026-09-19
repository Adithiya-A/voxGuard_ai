import io
import wave
import logging
from math import gcd
from typing import Tuple, List, Dict, Any
import numpy as np

logger = logging.getLogger("voxguard.audio")

def load_audio_bytes(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """
    Safely loads WAV audio bytes or raw PCM into a numpy float array [-1.0, 1.0].
    """
    try:
        with io.BytesIO(audio_bytes) as bio:
            with wave.open(bio, 'rb') as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())
                
                if sampwidth == 2:
                    dtype = np.int16
                elif sampwidth == 4:
                    dtype = np.int32
                elif sampwidth == 1:
                    dtype = np.uint8
                else:
                    dtype = np.int16
                
                data = np.frombuffer(frames, dtype=dtype)
                if n_channels > 1:
                    data = data.reshape(-1, n_channels).mean(axis=1)
                
                # Normalize to float [-1.0, 1.0]
                max_val = float(np.iinfo(dtype).max) if np.issubdtype(dtype, np.integer) else 1.0
                float_data = (data / max_val).astype(np.float32)
                return float_data, sample_rate
    except Exception:
        # Fallback: assume 16kHz 16-bit mono PCM
        data = np.frombuffer(audio_bytes, dtype=np.int16)
        float_data = (data / 32768.0).astype(np.float32)
        return float_data, 16000

def resample_to_16k(audio: np.ndarray, orig_sr: int) -> np.ndarray:
    """
    Resamples audio to 16,000 Hz using bandlimited polyphase filtering with an anti-aliasing filter.
    Prevents high-frequency aliasing and phase slip artifacts.
    """
    if orig_sr == 16000 or len(audio) == 0:
        return audio.astype(np.float32)
    
    try:
        import scipy.signal
        g = gcd(orig_sr, 16000)
        up = 16000 // g
        down = orig_sr // g
        resampled = scipy.signal.resample_poly(audio, up, down).astype(np.float32)
        return resampled
    except Exception:
        # Fallback linear interpolation
        target_length = int(round(len(audio) * 16000 / orig_sr))
        indices = np.linspace(0, len(audio) - 1, target_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

def compute_audio_diagnostics(audio: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
    """
    Computes statistical telemetry of audio waveform for diagnostic monitoring.
    Does NOT return or expose raw audio samples.
    """
    if audio is None or len(audio) == 0:
        return {
            "sample_rate": sample_rate,
            "sample_count": 0,
            "duration": 0.0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "rms": 0.0,
            "peak": 0.0,
            "clipping_pct": 0.0
        }

    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    clipping_pct = float(np.mean(np.abs(audio) >= 0.999) * 100.0)

    return {
        "sample_rate": sample_rate,
        "sample_count": len(audio),
        "duration": round(len(audio) / float(sample_rate), 3),
        "dtype": str(audio.dtype),
        "min": round(float(np.min(audio)), 4),
        "max": round(float(np.max(audio)), 4),
        "mean": round(float(np.mean(audio)), 6),
        "rms": round(rms, 4),
        "peak": round(peak, 4),
        "clipping_pct": round(clipping_pct, 2)
    }

def log_audio_diagnostics(tag: str, diag: Dict[str, Any]) -> None:
    """Logs audio diagnostics in SOC telemetry format."""
    logger.info(
        f"[AUDIO-DIAG] [{tag}] sr={diag.get('sample_rate')}Hz | duration={diag.get('duration')}s "
        f"| peak={diag.get('peak')} | rms={diag.get('rms')} | mean={diag.get('mean')} "
        f"| clipping={diag.get('clipping_pct')}%"
    )

def preprocess_for_speaker_model(
    audio: np.ndarray,
    sample_rate: int = 16000,
    tag: str = "PIPELINE"
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Canonical audio preprocessor used identically by both enrollment and live verification.
    Guarantees:
    1. 1D mono float32 waveform
    2. Zero DC offset
    3. Resampled to 16,000 Hz via anti-aliasing polyphase filtering
    4. Controlled amplitude within [-1.0, 1.0] without clipping
    5. Returns (processed_audio, diagnostics)
    """
    if audio is None or len(audio) == 0:
        return np.zeros(0, dtype=np.float32), compute_audio_diagnostics(np.zeros(0), 16000)

    processed = audio.copy().astype(np.float32)

    # 1. Multi-channel to mono
    if processed.ndim > 1:
        processed = np.mean(processed, axis=-1)

    # 2. Resample to 16 kHz if necessary (with anti-aliasing)
    if sample_rate != 16000:
        processed = resample_to_16k(processed, sample_rate)

    # 3. Remove DC offset
    processed = processed - np.mean(processed)

    # 4. Prevent clipping / scale if necessary
    peak = float(np.max(np.abs(processed))) if len(processed) > 0 else 0.0
    if peak > 1.0:
        processed = processed / peak

    diag = compute_audio_diagnostics(processed, 16000)
    log_audio_diagnostics(tag, diag)

    return processed, diag

def chunk_audio(audio: np.ndarray, sample_rate: int = 16000, chunk_seconds: float = 3.0) -> List[np.ndarray]:
    chunk_size = int(sample_rate * chunk_seconds)
    if len(audio) <= chunk_size:
        return [audio]
    return [audio[i:i + chunk_size] for i in range(0, len(audio), chunk_size)]
