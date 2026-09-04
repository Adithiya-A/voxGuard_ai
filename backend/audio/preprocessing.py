import io
import wave
import numpy as np
from typing import Tuple, List

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
    if orig_sr == 16000 or len(audio) == 0:
        return audio
    target_length = int(len(audio) * 16000 / orig_sr)
    indices = np.linspace(0, len(audio) - 1, target_length)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

def chunk_audio(audio: np.ndarray, sample_rate: int = 16000, chunk_seconds: float = 3.0) -> List[np.ndarray]:
    chunk_size = int(sample_rate * chunk_seconds)
    if len(audio) <= chunk_size:
        return [audio]
    return [audio[i:i + chunk_size] for i in range(0, len(audio), chunk_size)]
