"""
VoxGuard AI — Phase 3: Real Pretrained Speaker Biometrics Test Suite (ECAPA-TDNN)
Verifies:
1. Model initialization & lazy loading
2. Model caching & reuse
3. Model health state reporting
4. Empty audio rejection
5. Silence bypass (speech_detected=False)
6. Short/insufficient audio (< 0.25s)
7. 48 kHz to 16 kHz automatic resampling
8. Embedding generation
9. 192-dimensional unit-norm embedding
10. Dynamic speaker enrollment
11. Enrollment rejection of invalid audio
12. Biometric MATCH verification
13. Biometric MISMATCH verification
14. NOT_ENROLLED status for unknown identities
15. Configurable decision threshold
16. Model error resilience (MODEL_ERROR)
17. WebSocket integration with speaker telemetry
18. AASIST + ECAPA-TDNN coexistence in stream processor
19. Absence of mock data in live sessions
20. Voice Clone Paradox detection and critical trust drop
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import time
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.speaker_verifier import speaker_verifier, SpeakerVerifier
from backend.audio.stream_processor import stream_processor

class TestPhase3SpeakerBiometrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Pre-generate synthetic voiced tones for testing
        sr = 16000
        t = np.linspace(0, 3.0, sr * 3, endpoint=False, dtype=np.float32)
        # Tone A (e.g. 130 Hz baritone harmonic)
        cls.audio_speaker_a = (
            0.6 * np.sin(2 * np.pi * 130 * t) +
            0.3 * np.sin(4 * np.pi * 130 * t)
        ).astype(np.float32)
        # Tone B (e.g. 350 Hz soprano harmonic)
        cls.audio_speaker_b = (
            0.6 * np.sin(2 * np.pi * 350 * t) +
            0.3 * np.sin(4 * np.pi * 350 * t)
        ).astype(np.float32)

    # 1. Model Initialization
    def test_model_initialization(self):
        self.assertEqual(speaker_verifier.architecture, "ECAPA-TDNN")
        self.assertEqual(speaker_verifier.embedding_dimension, 192)
        self.assertIn(speaker_verifier.device, ["cpu", "cuda"])
        self.assertEqual(speaker_verifier.license, "Apache-2.0")

    # 2. Model Reuse (Caching)
    def test_model_reuse(self):
        speaker_verifier.load_model()
        initial_instance = speaker_verifier._classifier
        self.assertIsNotNone(initial_instance)

        # Trigger another extraction
        _ = speaker_verifier.extract_embedding(self.audio_speaker_a, sample_rate=16000)
        self.assertIs(speaker_verifier._classifier, initial_instance, "Model must remain cached and reused")

    # 3. Model Availability & State Reporting
    def test_model_availability(self):
        state = speaker_verifier.get_state()
        self.assertTrue(state["available"])
        self.assertEqual(state["model"], "ECAPA-TDNN")
        self.assertEqual(state["embedding_dimension"], 192)
        self.assertGreaterEqual(state["enrolled_speakers_count"], 2)

    # 4. Empty Audio
    def test_empty_audio(self):
        emb = speaker_verifier.extract_embedding(np.zeros(0, dtype=np.float32), sample_rate=16000)
        self.assertIsNone(emb)
        res = speaker_verifier.verify_speaker(np.zeros(0, dtype=np.float32), claimed_speaker_id="cfo_arun")
        self.assertEqual(res["status"], "INCONCLUSIVE")
        self.assertFalse(res["available"])

    # 5. Silence Bypass
    def test_silence_bypass(self):
        res = speaker_verifier.verify_speaker(
            self.audio_speaker_a,
            claimed_speaker_id="cfo_arun",
            speech_detected=False
        )
        self.assertEqual(res["status"], "NO_SPEECH")
        self.assertFalse(res["available"])
        self.assertEqual(res["inference_ms"], 0.0)

    # 6. Short / Insufficient Audio (< 0.25s)
    def test_short_insufficient_audio(self):
        short_audio = np.ones(1000, dtype=np.float32) * 0.5  # < 4000 samples
        res = speaker_verifier.verify_speaker(
            short_audio,
            claimed_speaker_id="cfo_arun",
            speech_detected=True
        )
        self.assertEqual(res["status"], "INCONCLUSIVE")
        self.assertFalse(res["available"])

    # 7. 48 kHz to 16 kHz Processing
    def test_audio_resampling_48k(self):
        t_48k = np.linspace(0, 3.0, 48000 * 3, endpoint=False, dtype=np.float32)
        audio_48k = (0.5 * np.sin(2 * np.pi * 130 * t_48k)).astype(np.float32)
        res = speaker_verifier.verify_speaker(
            audio_48k,
            claimed_speaker_id="cfo_arun",
            sample_rate=48000,
            speech_detected=True
        )
        self.assertTrue(res["available"])
        self.assertIn(res["status"], ["MATCH", "MISMATCH"])

    # 8. Embedding Generation
    def test_embedding_generation(self):
        emb = speaker_verifier.extract_embedding(self.audio_speaker_a, sample_rate=16000)
        self.assertIsNotNone(emb)
        self.assertIsInstance(emb, np.ndarray)

    # 9. Embedding Dimensionality & Unit Norm
    def test_embedding_dimensionality(self):
        emb = speaker_verifier.extract_embedding(self.audio_speaker_a, sample_rate=16000)
        self.assertEqual(emb.shape, (192,))
        norm = np.linalg.norm(emb)
        self.assertAlmostEqual(float(norm), 1.0, places=5)

    # 10. Speaker Enrollment
    def test_speaker_enrollment(self):
        speaker_id = f"exec_test_{int(time.time())}"
        enroll_res = speaker_verifier.enroll_speaker(
            speaker_id=speaker_id,
            display_name="Test Executive",
            audio=self.audio_speaker_a,
            sample_rate=16000
        )
        self.assertTrue(enroll_res["success"])
        self.assertEqual(enroll_res["speaker_id"], speaker_id)
        self.assertEqual(enroll_res["embedding_dimension"], 192)
        self.assertIn(speaker_id, speaker_verifier.enrolled_speakers)

    # 11. Enrollment with Invalid Audio
    def test_enrollment_invalid_audio(self):
        enroll_res = speaker_verifier.enroll_speaker(
            speaker_id="bad_exec",
            display_name="Bad Audio Executive",
            audio=np.zeros(100, dtype=np.float32),
            sample_rate=16000
        )
        self.assertFalse(enroll_res["success"])
        self.assertIn("error", enroll_res)

    # 12. Verification with Enrolled Speaker (MATCH)
    def test_verification_enrolled_speaker(self):
        speaker_id = "test_match_exec"
        speaker_verifier.enroll_speaker(
            speaker_id=speaker_id,
            display_name="Matched Executive",
            audio=self.audio_speaker_a,
            sample_rate=16000
        )
        # Verify with identical reference audio
        res = speaker_verifier.verify_speaker(
            self.audio_speaker_a,
            claimed_speaker_id=speaker_id,
            threshold=0.80
        )
        self.assertTrue(res["available"])
        self.assertEqual(res["status"], "MATCH")
        self.assertGreater(res["similarity"], 0.95)

    # 13. Verification with Unknown / Different Speaker (MISMATCH)
    def test_verification_mismatch_speaker(self):
        speaker_id = "test_mismatch_exec"
        speaker_verifier.enroll_speaker(
            speaker_id=speaker_id,
            display_name="Executive Profile A",
            audio=self.audio_speaker_a,
            sample_rate=16000
        )
        # Verify with very different frequency profile B
        res = speaker_verifier.verify_speaker(
            self.audio_speaker_b,
            claimed_speaker_id=speaker_id,
            threshold=0.85
        )
        self.assertTrue(res["available"])
        self.assertEqual(res["status"], "MISMATCH")

    # 14. NOT_ENROLLED Status
    def test_not_enrolled_speaker(self):
        res = speaker_verifier.verify_speaker(
            self.audio_speaker_a,
            claimed_speaker_id="nonexistent_alien_speaker_404"
        )
        self.assertEqual(res["status"], "NOT_ENROLLED")
        self.assertEqual(res["similarity"], 0.0)

    # 15. Configurable Decision Threshold
    def test_configurable_threshold(self):
        speaker_id = "test_threshold_exec"
        speaker_verifier.enroll_speaker(
            speaker_id=speaker_id,
            display_name="Threshold Executive",
            audio=self.audio_speaker_a,
            sample_rate=16000
        )
        # Very high threshold (impossible for different tone) -> MISMATCH
        res_high = speaker_verifier.verify_speaker(
            self.audio_speaker_b,
            claimed_speaker_id=speaker_id,
            threshold=0.99
        )
        self.assertEqual(res_high["status"], "MISMATCH")

        # Extremely low threshold -> MATCH
        res_low = speaker_verifier.verify_speaker(
            self.audio_speaker_b,
            claimed_speaker_id=speaker_id,
            threshold=0.10
        )
        self.assertEqual(res_low["status"], "MATCH")

    # 16. Model Error Handling
    def test_model_error_handling(self):
        with patch.object(speaker_verifier, "extract_embedding", side_effect=RuntimeError("Simulated ECAPA Error")):
            res = speaker_verifier.verify_speaker(
                self.audio_speaker_a,
                claimed_speaker_id="cfo_arun",
                speech_detected=True
            )
            self.assertEqual(res["status"], "MODEL_ERROR")
            self.assertFalse(res["available"])
            self.assertIn("Simulated ECAPA Error", res["error"])

    # 17. WebSocket Integration with Speaker Telemetry
    def test_websocket_stream_integration(self):
        call_id = f"WS-PHASE3-{int(time.time())}"
        with self.client.websocket_connect(f"/ws/call/{call_id}") as ws:
            conn_msg = ws.receive_json()
            self.assertEqual(conn_msg["type"], "CONNECTION_ESTABLISHED")

            # Start audio stream claiming CFO Arun
            ws.send_json({
                "type": "START_AUDIO_STREAM",
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm_s16le",
                "claimed_speaker_id": "cfo_arun"
            })
            started_msg = ws.receive_json()
            self.assertEqual(started_msg["type"], "AUDIO_STREAM_STARTED")
            self.assertEqual(started_msg["claimed_speaker_id"], "cfo_arun")
            sess_msg = ws.receive_json()
            self.assertEqual(sess_msg["type"], "SESSION_STARTED")

            # Send 1.5 seconds of PCM16 audio
            pcm_bytes = (self.audio_speaker_a[:24000] * 32767).astype(np.int16).tobytes()
            ws.send_bytes(pcm_bytes)

            analysis = ws.receive_json()
            self.assertEqual(analysis["type"], "AUDIO_ANALYSIS")
            self.assertIn("speaker_verification", analysis["data"])
            self.assertIn("speaker", analysis["data"])
            self.assertIn("voice_clone_paradox", analysis["data"])
            self.assertIn("speaker", analysis["data"]["latency_ms"])

            # Stop audio stream
            ws.send_json({"type": "STOP_AUDIO_STREAM"})
            stopped_msg = None
            for _ in range(10):
                msg = ws.receive_json()
                if msg.get("type") == "AUDIO_STREAM_STOPPED":
                    stopped_msg = msg
                    break
            self.assertIsNotNone(stopped_msg)
            self.assertEqual(stopped_msg["type"], "AUDIO_STREAM_STOPPED")

    # 18. AASIST + ECAPA Telemetry Coexistence
    def test_aasist_and_speaker_coexistence(self):
        call_id = f"COEXIST-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, claimed_speaker_id="cfo_arun")
        pcm_bytes = (self.audio_speaker_a[:24000] * 32767).astype(np.int16).tobytes()
        analysis = stream_processor.process_chunk(call_id, pcm_bytes)
        self.assertIsNotNone(analysis)

        data = analysis["data"]
        # Both models must be present
        self.assertIn("anti_spoof", data["voice_authenticity"])
        self.assertIn("speaker_verification", data)
        self.assertEqual(data["voice_authenticity"]["anti_spoof"]["model"], "AASIST")
        self.assertEqual(data["speaker_verification"]["model"], "ECAPA-TDNN")
        stream_processor.stop_call_stream(call_id)

    # 19. Absence of Mock Similarity in Live Mode
    def test_live_session_no_mock_similarity(self):
        call_id = f"NO-MOCK-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, claimed_speaker_id="cfo_arun")
        # Send silence
        silent_pcm = np.zeros(24000, dtype=np.int16).tobytes()
        analysis = stream_processor.process_chunk(call_id, silent_pcm)
        self.assertIsNotNone(analysis)
        # In live mode with silence, similarity must NOT be the mock 94.2
        speaker_data = analysis["data"]["speaker"]
        self.assertNotEqual(speaker_data.get("speaker_similarity"), 94.2)
        stream_processor.stop_call_stream(call_id)

    # 20. Voice Clone Paradox Detection
    def test_voice_clone_paradox_detection(self):
        # When AASIST reports SPOOF and Speaker reports MATCH, trust score must drop to CRITICAL
        trust = stream_processor._calculate_preliminary_trust(
            anti_spoof_result={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.95},
            speaker_result={"available": True, "status": "MATCH", "similarity_pct": 92.0},
            speech_detected=True,
            possible_voice_clone=True
        )
        self.assertEqual(trust["risk_level"], "CRITICAL")
        self.assertLessEqual(trust["score"], 20)
        self.assertEqual(trust["trust_state"], "ATTACK_FLAGGED")
        self.assertIn("Voice Clone Paradox", trust["label"])

if __name__ == "__main__":
    unittest.main()
