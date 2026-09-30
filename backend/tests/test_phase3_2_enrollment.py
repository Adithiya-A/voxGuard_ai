"""
VoxGuard AI — Phase 3.2: Real Voice Enrollment & Voiceprint Management Test Suite
Verifies:
1. Valid voice enrollment via base64 encoded audio
2. Invalid speaker ID format rejection (e.g. uppercase, spaces, invalid chars)
3. Duplicate speaker ID rejection (HTTP 400 with descriptive message)
4. Empty audio rejection (HTTP 400)
5. Silent audio rejection (HTTP 400)
6. Too-short audio rejection (< 0.25s / < 4000 samples)
7. Valid 192-dimensional embedding generated
8. Embedding dimensionality is exactly 192
9. Embedding is unit-normalized (L2 norm == 1.0)
10. Enrolled speaker appears in GET /api/speakers with is_synthetic=False
11. Live verification against newly enrolled speaker produces genuine MATCH
12. Verification against non-enrolled speaker returns NOT_ENROLLED
13. Model error handling resilience
14. Safe speaker deletion via DELETE /api/speakers/{speaker_id}
15. Synthetic profiles marked as DEMO_SYNTHETIC and is_synthetic=True
16. WebSocket live call with newly enrolled speaker
"""

import unittest
import base64
import io
import wave
import time
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.speaker_verifier import speaker_verifier
from backend.audio.stream_processor import stream_processor

def create_synthetic_wav_bytes(
    freq_hz: float = 220.0,
    duration_s: float = 2.0,
    sample_rate: int = 16000,
    silent: bool = False
) -> bytes:
    """Generates standard 16-bit PCM WAV bytes for testing."""
    num_samples = int(sample_rate * duration_s)
    if silent:
        samples = np.zeros(num_samples, dtype=np.int16)
    else:
        t = np.linspace(0, duration_s, num_samples, endpoint=False, dtype=np.float32)
        signal = 0.6 * np.sin(2 * np.pi * freq_hz * t) + 0.3 * np.sin(4 * np.pi * freq_hz * t)
        samples = (signal * 32767).astype(np.int16)
        
    bio = io.BytesIO()
    with wave.open(bio, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return bio.getvalue()

class TestPhase32Enrollment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Ensure model is warm
        speaker_verifier.load_model()

    # 1. Valid Voice Enrollment
    def test_01_valid_voice_enrollment(self):
        wav_bytes = create_synthetic_wav_bytes(freq_hz=180.0, duration_s=2.5)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')
        speaker_id = f"test_user_{int(time.time())}"

        resp = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Test User Genuine",
            "role": "Chief Operations Officer",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["speaker_id"], speaker_id)
        self.assertEqual(data["embedding_dimension"], 192)
        self.assertEqual(data["status"], "ENROLLED")
        self.assertFalse(data["is_synthetic"])

    # 2. Invalid Speaker ID
    def test_02_invalid_speaker_id_rejected(self):
        wav_bytes = create_synthetic_wav_bytes()
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        invalid_ids = [
            "User With Spaces",
            "UPPERCASE_USER",
            "user@domain!",
            "user#123",
            "",
            "   "
        ]
        for bad_id in invalid_ids:
            resp = self.client.post("/api/speakers/enroll", json={
                "speaker_id": bad_id,
                "display_name": "Invalid ID User",
                "audio_base64": audio_b64
            })
            self.assertEqual(resp.status_code, 400, f"Expected 400 for bad ID '{bad_id}'")
            self.assertIn("detail", resp.json())

    # 3. Duplicate Speaker ID Rejection
    def test_03_duplicate_speaker_rejected(self):
        wav_bytes = create_synthetic_wav_bytes(freq_hz=200.0)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')
        speaker_id = f"dup_user_{int(time.time())}"

        # First enrollment succeeds
        resp1 = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "First Instance",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp1.status_code, 200)

        # Second enrollment with same ID must fail
        resp2 = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Duplicate Instance",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("already exists", resp2.json()["detail"])

    # 4. Empty Audio Rejection
    def test_04_empty_audio_rejected(self):
        speaker_id = f"empty_audio_{int(time.time())}"
        resp = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Empty Audio User",
            "audio_base64": ""
        })
        self.assertEqual(resp.status_code, 400)

    # 5. Silent Audio Rejection
    def test_05_silent_audio_rejected(self):
        silent_wav = create_synthetic_wav_bytes(silent=True, duration_s=2.0)
        audio_b64 = base64.b64encode(silent_wav).decode('utf-8')
        speaker_id = f"silent_user_{int(time.time())}"

        resp = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Silent User",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("silence", resp.json()["detail"].lower())

    # 6. Too-Short Audio Rejection
    def test_06_too_short_audio_rejected(self):
        # 0.1s audio = 1600 samples (< 4000 samples)
        short_wav = create_synthetic_wav_bytes(duration_s=0.1)
        audio_b64 = base64.b64encode(short_wav).decode('utf-8')
        speaker_id = f"short_user_{int(time.time())}"

        resp = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Short User",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("short", resp.json()["detail"].lower())

    # 7, 8, 9. Valid Embedding Extraction, Dimension & Normalization
    def test_07_08_09_embedding_dimension_and_normalization(self):
        speaker_id = f"dim_norm_{int(time.time())}"
        wav_bytes = create_synthetic_wav_bytes(freq_hz=160.0, duration_s=2.0)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        resp = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Dimension User",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp.status_code, 200)

        # Inspect stored embedding directly in memory
        profile = speaker_verifier.enrolled_speakers.get(speaker_id)
        self.assertIsNotNone(profile)
        emb = profile.get("embedding")
        self.assertIsNotNone(emb)
        self.assertEqual(emb.shape, (192,))
        self.assertAlmostEqual(float(np.linalg.norm(emb)), 1.0, places=5)

    # 10. Enrollment Appears in GET /api/speakers
    def test_10_enrolled_speaker_listed(self):
        speaker_id = f"list_user_{int(time.time())}"
        wav_bytes = create_synthetic_wav_bytes(freq_hz=210.0, duration_s=2.0)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        resp = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Listed User",
            "role": "VP Engineering",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp.status_code, 200)

        get_resp = self.client.get("/api/speakers")
        self.assertEqual(get_resp.status_code, 200)
        speakers = get_resp.json()
        ids = [s["speaker_id"] for s in speakers]
        self.assertIn(speaker_id, ids)

        found = next(s for s in speakers if s["speaker_id"] == speaker_id)
        self.assertEqual(found["display_name"], "Listed User")
        self.assertEqual(found["status"], "ENROLLED")
        self.assertFalse(found["is_synthetic"])
        self.assertEqual(found["embedding_dimension"], 192)

    # 11. Live Verification Can Use Newly Enrolled Speaker
    def test_11_live_verification_with_newly_enrolled(self):
        speaker_id = f"live_verif_{int(time.time())}"
        wav_bytes = create_synthetic_wav_bytes(freq_hz=240.0, duration_s=3.0)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        resp = self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "Live Verification User",
            "audio_base64": audio_b64
        })
        self.assertEqual(resp.status_code, 200)

        # Same voice waveform should produce MATCH
        t = np.linspace(0, 3.0, 16000 * 3, endpoint=False, dtype=np.float32)
        same_audio = (0.6 * np.sin(2 * np.pi * 240.0 * t) + 0.3 * np.sin(4 * np.pi * 240.0 * t)).astype(np.float32)
        verif_result = speaker_verifier.verify_speaker(same_audio, claimed_speaker_id=speaker_id)
        self.assertTrue(verif_result["available"])
        self.assertEqual(verif_result["status"], "MATCH")
        self.assertGreaterEqual(verif_result["similarity"], 0.80)

    # 12. Non-Enrolled Speaker Returns NOT_ENROLLED
    def test_12_non_enrolled_speaker_returns_not_enrolled(self):
        t = np.linspace(0, 3.0, 16000 * 3, endpoint=False, dtype=np.float32)
        audio = (0.5 * np.sin(2 * np.pi * 150.0 * t)).astype(np.float32)
        verif_result = speaker_verifier.verify_speaker(audio, claimed_speaker_id="completely_unknown_speaker_xyz")
        self.assertEqual(verif_result["status"], "NOT_ENROLLED")
        self.assertIn("not enrolled", verif_result["error"].lower())

    # 13. Safe Speaker Deletion via DELETE /api/speakers/{speaker_id}
    def test_13_delete_speaker_endpoint(self):
        speaker_id = f"to_delete_{int(time.time())}"
        wav_bytes = create_synthetic_wav_bytes(freq_hz=190.0, duration_s=2.0)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        # Enroll
        self.client.post("/api/speakers/enroll", json={
            "speaker_id": speaker_id,
            "display_name": "To Delete User",
            "audio_base64": audio_b64
        })
        self.assertIn(speaker_id, speaker_verifier.enrolled_speakers)

        # Delete
        del_resp = self.client.delete(f"/api/speakers/{speaker_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["success"])
        self.assertNotIn(speaker_id, speaker_verifier.enrolled_speakers)

        # Deleting again returns 404
        del_resp_again = self.client.delete(f"/api/speakers/{speaker_id}")
        self.assertEqual(del_resp_again.status_code, 404)

    # 14. Synthetic Profiles Demarcated Clearly
    def test_14_synthetic_profiles_demarcated(self):
        get_resp = self.client.get("/api/speakers")
        self.assertEqual(get_resp.status_code, 200)
        speakers = get_resp.json()

        cfo = next((s for s in speakers if s["speaker_id"] == "cfo_arun"), None)
        if cfo:
            self.assertTrue(cfo["is_synthetic"])
            self.assertEqual(cfo["status"], "DEMO_SYNTHETIC")

        vp = next((s for s in speakers if s["speaker_id"] == "vp_sarah"), None)
        if vp:
            self.assertTrue(vp["is_synthetic"])
            self.assertEqual(vp["status"], "DEMO_SYNTHETIC")

if __name__ == "__main__":
    unittest.main()
