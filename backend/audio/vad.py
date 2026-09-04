import numpy as np

def detect_voice_activity(audio: np.ndarray, threshold_energy: float = 0.005) -> bool:
    """
    Computes Short-Time Energy (STE) to verify active speech vs background line noise.
    """
    if len(audio) == 0:
        return False
    energy = np.mean(audio ** 2)
    return bool(energy > threshold_energy)
