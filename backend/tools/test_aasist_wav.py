"""
Real Microphone & Offline Audio Forensic Diagnostic Tool.
Usage:
    python -m backend.tools.test_aasist_wav <path_to_wav> [--speaker <speaker_id>] [--transcribe]
"""

import os
import sys
import argparse
import soundfile as sf
import numpy as np

from backend.models.deepfake_detector import deepfake_detector, AASIST_INPUT_SAMPLES
from backend.models.speaker_verifier import speaker_verifier
from backend.models.transcription import transcription_service
from backend.audio.preprocessing import compute_audio_diagnostics


def run_diagnostic(
    wav_path: str,
    claimed_speaker_id: str = "cfo_arun",
    transcribe: bool = False
) -> int:
    if not os.path.exists(wav_path):
        print(f"[ERROR] Audio file not found: {wav_path}")
        return 2

    print("=" * 65)
    print(" VOXGUARD AI — AUDIO & AASIST FORENSIC DIAGNOSTIC")
    print("=" * 65)
    print(f"Target File      : {wav_path}")

    # 1. Load Audio
    data, sr = sf.read(wav_path)
    if data.ndim > 1:
        data = np.mean(data, axis=-1)
    data = data.astype(np.float32)

    diag = compute_audio_diagnostics(data, sample_rate=sr)
    print(f"Sample Rate      : {diag['sample_rate']} Hz")
    print(f"Duration         : {diag['duration']} s ({diag['sample_count']} samples)")
    print(f"Peak Amplitude   : {diag['peak']:.4f}")
    print(f"RMS Energy       : {diag['rms']:.4f}")
    print(f"Mean DC Offset   : {diag['mean']:.6f}")
    print(f"Clipped Samples  : {diag['clipped_sample_count']} ({diag['clipping_percentage']}%)")
    print("-" * 65)

    # 2. AASIST Anti-Spoof Inference
    deepfake_detector.load_model()
    result = deepfake_detector.analyze(data, sample_rate=sr, speech_detected=True)

    prediction = result.get("prediction", "UNKNOWN")
    spoof_prob = result.get("spoof_probability")
    genuine_prob = result.get("genuine_probability")
    bonafide_score = result.get("score")

    print(f"AASIST Model     : {result.get('model')} ({result.get('model_version')})")
    print(f"Device           : {result.get('device')}")
    print(f"Inference Time   : {result.get('inference_ms')} ms")
    print(f"AASIST Prediction: {prediction}")
    if spoof_prob is not None:
        print(f"Spoof Probability: {spoof_prob * 100:.2f}%")
        print(f"Bonafide Prob    : {genuine_prob * 100:.2f}%")
        print(f"Raw Bonafide Logit: {bonafide_score:.4f}")
    else:
        print(f"Status           : {result.get('status')}")
    print("-" * 65)

    # 3. ECAPA Speaker Verification
    if claimed_speaker_id:
        spk_res = speaker_verifier.verify_speaker(data, claimed_speaker_id=claimed_speaker_id, sample_rate=sr)
        print(f"Claimed Speaker  : {claimed_speaker_id}")
        print(f"ECAPA Status     : {spk_res.get('status')}")
        print(f"Similarity Score : {spk_res.get('similarity_score')}")
        print(f"ECAPA Decision   : {spk_res.get('decision') or spk_res.get('status')}")
        print("-" * 65)

    # 4. Optional Whisper Transcription
    if transcribe:
        asr_res = transcription_service.transcribe_audio(data, sample_rate=sr, call_id="DIAG")
        print(f"Whisper Model    : {asr_res.get('model_size')}")
        print(f"Language Detected: {asr_res.get('language')}")
        print(f"Transcript       : \"{asr_res.get('text')}\"")
        print("-" * 65)

    print("SUMMARY VERDICT:")
    if prediction == "BONAFIDE":
        print(">> [PASS] Audio passes AASIST anti-spoof check (BONAFIDE).")
        return 0
    elif prediction == "SPOOF":
        print(">> [FAIL] Audio classified as SPOOF (Synthetic / Replay / Incompatible distribution).")
        return 1
    else:
        print(f">> [INCONCLUSIVE] AASIST result: {prediction} ({result.get('status')})")
        return 0


def main():
    parser = argparse.ArgumentParser(description="VoxGuard AASIST Audio Diagnostic Tool")
    parser.add_argument("wav_path", nargs="?", default="backend/tests/fixtures/genuine_speech.wav", help="Path to WAV audio file")
    parser.add_argument("--speaker", default="cfo_arun", help="Claimed speaker ID for ECAPA verification")
    parser.add_argument("--transcribe", action="store_true", help="Also run faster-whisper transcription")

    args = parser.parse_args()
    sys.exit(run_diagnostic(args.wav_path, args.speaker, args.transcribe))


if __name__ == "__main__":
    main()
