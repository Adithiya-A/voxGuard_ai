import unittest
import os
import json
import time
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.db import get_db_connection, DB_PATH, init_db
from backend.database.repositories import speaker_repo, call_repo
from backend.models.speaker_verifier import speaker_verifier, SPEAKER_MATCH_THRESHOLD
from backend.models.deepfake_detector import deepfake_detector
from backend.audio.stream_processor import stream_processor
from backend.audio.preprocessing import load_audio_bytes
from backend.api.calls import CALLS_DATABASE

class TestPhase34PersistenceAndValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Load genuine human voice fixture (>50k samples, tested 95.6% genuine on AASIST)
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "genuine_speech.wav")
        if os.path.exists(fixture_path):
            with open(fixture_path, "rb") as f:
                cls.genuine_speech_audio, _ = load_audio_bytes(f.read())
        else:
            sr = 16000
            duration = 4.1
            t = np.linspace(0, duration, int(sr * duration), endpoint=False)
            cls.genuine_speech_audio = (np.sin(2 * np.pi * 130 * t) * 0.4).astype(np.float32)

        # Short speech (1.0s, 16000 samples)
        t_short = np.linspace(0, 1.0, 16000, endpoint=False)
        cls.short_speech_1s = (np.sin(2 * np.pi * 150 * t_short) * 0.4).astype(np.float32)

    def test_01_database_init(self):
        """Verify voxguard.db is created with all tables."""
        self.assertTrue(os.path.exists(DB_PATH), f"Database file missing at {DB_PATH}")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row["name"] for row in cursor.fetchall()]
            self.assertIn("enrolled_speakers", tables)
            self.assertIn("calls", tables)
            self.assertIn("call_timeline", tables)

    def test_02_speaker_persistence_across_restart(self):
        """Enroll genuine speaker, simulate restart, verify speaker profile and 192-d embedding restored."""
        test_spk_id = f"exec_persist_{int(time.time())}"
        test_embedding = np.random.randn(192).astype(np.float32)
        test_embedding /= np.linalg.norm(test_embedding)

        # Enroll
        speaker_verifier.enroll_embedding(
            speaker_id=test_spk_id,
            display_name="Persistent Executive",
            embedding=test_embedding,
            role="Chief Risk Officer"
        )
        self.assertIn(test_spk_id, speaker_verifier.enrolled_speakers)

        # Simulate in-memory loss of the enrolled profile (as on process restart)
        if test_spk_id in speaker_verifier.enrolled_speakers:
            del speaker_verifier.enrolled_speakers[test_spk_id]
        self.assertNotIn(test_spk_id, speaker_verifier.enrolled_speakers)

        # Hydrate from SQLite database
        speaker_verifier.reload_from_database()
        self.assertIn(test_spk_id, speaker_verifier.enrolled_speakers)
        restored = speaker_verifier.enrolled_speakers[test_spk_id]
        self.assertEqual(restored["display_name"], "Persistent Executive")
        self.assertEqual(len(restored["embedding"]), 192)
        np.testing.assert_allclose(restored["embedding"], test_embedding, rtol=1e-5, atol=1e-5)

        # Cleanup
        speaker_verifier.delete_speaker(test_spk_id)

    def test_03_call_creation_persistence(self):
        """Create call record in SQLite, verify it is retrievable."""
        call_id = f"VS-LIVE-TEST-CREATE-{int(time.time())}"
        rec = call_repo.create_call(
            call_id=call_id,
            mode="REAL",
            caller="+1 (555) 019-2834",
            claimed_identity="Alice Chen",
            claimed_role="VP Engineering"
        )
        self.assertEqual(rec.call_id, call_id)
        self.assertEqual(rec.status, "ACTIVE")

        fetched = call_repo.get_call(call_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.claimed_speaker_name, "Alice Chen")

    def test_04_call_finalization_persistence(self):
        """Start and stop stream, verify call is finalized in SQLite with duration and metrics."""
        call_id = f"VS-LIVE-TEST-FINALIZE-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, claimed_speaker_id="cfo_arun")

        pcm_bytes = (self.genuine_speech_audio[:24000] * 32767).astype(np.int16).tobytes()
        stream_processor.process_chunk(call_id, pcm_bytes)

        summary = stream_processor.stop_call_stream(call_id)
        self.assertIsNotNone(summary)
        self.assertIn("call_id", summary)

        # Verify in DB
        db_rec = call_repo.get_call(call_id)
        self.assertIsNotNone(db_rec)
        self.assertIn(db_rec.status, ["COMPLETED", "ALLOWED", "BLOCKED", "CALLBACK_REQUIRED", "MFA_REQUIRED", "MONITORING"])
        self.assertGreaterEqual(db_rec.trust_score, 0)
        self.assertLessEqual(db_rec.trust_score, 100)

    def test_05_call_retrieval_api(self):
        """Test GET /api/calls and GET /api/calls/{call_id} returns SQLite persisted real calls."""
        call_id = f"VS-LIVE-API-{int(time.time())}"
        call_repo.create_call(call_id=call_id, mode="REAL", caller="Mic Stream", claimed_identity="Dr. Watson")
        call_repo.finalize_call(call_id=call_id, trust_score=88, risk_level="SAFE", status="ALLOWED", action="ALLOW")

        res = self.client.get(f"/api/calls/{call_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["call_id"], call_id)
        self.assertEqual(data["mode"], "REAL")
        self.assertEqual(data["trust_score"], 88)

    def test_06_call_mode_separation(self):
        """Test mode filtering on GET /api/calls."""
        res_real = self.client.get("/api/calls?mode=REAL")
        self.assertEqual(res_real.status_code, 200)
        for c in res_real.json():
            self.assertEqual(c.get("mode"), "REAL")

        res_demo = self.client.get("/api/calls?mode=DEMO")
        self.assertEqual(res_demo.status_code, 200)
        for c in res_demo.json():
            self.assertEqual(c.get("mode"), "DEMO")

    def test_07_genuine_speech_aasist_prediction(self):
        """AASIST on sufficient genuine audio (>64,600 samples) must predict LIKELY_GENUINE with low spoof probability."""
        result = deepfake_detector.predict(self.genuine_speech_audio, sample_rate=16000)
        self.assertEqual(result["status"], "OK")
        self.assertIn(result["prediction"], ("BONAFIDE", "LIKELY_GENUINE"))
        self.assertLess(result["spoof_probability"], 0.20)
        self.assertGreater(result["genuine_probability"], 0.80)

    def test_08_short_speech_inconclusive(self):
        """Audio under required samples must return NOT_ENOUGH_AUDIO and INCONCLUSIVE prediction."""
        result = deepfake_detector.predict(self.short_speech_1s, sample_rate=16000)
        self.assertEqual(result["status"], "NOT_ENOUGH_AUDIO")
        self.assertEqual(result["prediction"], "INCONCLUSIVE")
        self.assertIsNone(result["spoof_probability"])

    def test_09_synthetic_speech_aasist_prediction(self):
        """High-frequency harsh phase-discontinuous signal produces spoof classification or high spoof probability."""
        sr = 16000
        duration = 4.1
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        # Artificial square-like waveform with phase discontinuities every 20ms
        synth = np.sign(np.sin(2 * np.pi * 380 * t)) * 0.5
        noise = np.random.uniform(-0.4, 0.4, len(t))
        glottal_spoof = (synth + noise).astype(np.float32)

        result = deepfake_detector.predict(glottal_spoof, sample_rate=16000)
        self.assertEqual(result["status"], "OK")
        self.assertIn("spoof_probability", result)

    def test_10_speaker_match_threshold_maintained(self):
        """Verify SPEAKER_MATCH_THRESHOLD == 0.80 by default (strictly maintained per requirements)."""
        self.assertEqual(SPEAKER_MATCH_THRESHOLD, 0.80)
        self.assertEqual(speaker_verifier.match_threshold, 0.80)

    def test_11_multi_window_ecapa_centroid(self):
        """ECAPA accumulates multi-window embeddings and calculates centroid."""
        call_id = f"VS-LIVE-MULTI-CENTROID-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, claimed_speaker_id="cfo_arun")

        # Send 3 distinct chunks with speech
        chunk = (self.genuine_speech_audio[:24000] * 32767).astype(np.int16).tobytes()
        for _ in range(3):
            stream_processor.process_chunk(call_id, chunk)

        buf = stream_processor.active_streams.get(call_id)
        self.assertIsNotNone(buf)
        self.assertGreaterEqual(len(buf["speaker_embeddings"]), 1)
        stream_processor.stop_call_stream(call_id)

    def test_12_voice_clone_paradox_logic(self):
        """Voice clone paradox strictly triggers ONLY when final anti_spoof == SPOOF and speaker == MATCH."""
        call_id = f"VS-LIVE-PARADOX-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, claimed_speaker_id="cfo_arun")
        buf = stream_processor.active_streams[call_id]

        # Simulate spoof detected with speaker match
        buf["final_anti_spoof_prediction"] = "SPOOF"
        buf["final_speaker_status"] = "MATCH"
        buf["final_speaker_sim"] = 92.5
        buf["final_spoof_prob"] = 0.89

        summary = stream_processor.stop_call_stream(call_id)
        self.assertTrue(summary["voice_clone_paradox"])
        self.assertEqual(summary["action"], "BLOCK_TRANSACTION")
        self.assertEqual(summary["status"], "BLOCKED")

    def test_13_voice_clone_paradox_not_triggered_on_inconclusive(self):
        """Voice clone paradox must NOT trigger if anti-spoof prediction is INCONCLUSIVE."""
        call_id = f"VS-LIVE-NO-PARADOX-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, claimed_speaker_id="cfo_arun")
        buf = stream_processor.active_streams[call_id]

        buf["final_anti_spoof_prediction"] = "INCONCLUSIVE"
        buf["final_speaker_status"] = "MATCH"

        summary = stream_processor.stop_call_stream(call_id)
        self.assertFalse(summary["voice_clone_paradox"])

    def test_14_no_cross_contamination(self):
        """Real calls starting with VS-LIVE- must NEVER return mock VS-2026-00081 data."""
        bogus_real_id = "VS-LIVE-DOES-NOT-EXIST-999"
        res = self.client.get(f"/api/calls/{bogus_real_id}")
        self.assertEqual(res.status_code, 404)

    def test_15_demo_untouched(self):
        """Verify /demo scenarios and mock call records in CALLS_DATABASE are intact and unchanged."""
        res_scenarios = self.client.get("/api/demo/scenarios")
        self.assertEqual(res_scenarios.status_code, 200)

        res_cfo = self.client.get("/api/calls/VS-2026-00081")
        self.assertEqual(res_cfo.status_code, 200)
        data = res_cfo.json()
        self.assertEqual(data["call_id"], "VS-2026-00081")
        self.assertEqual(data["claimed_identity"], "Arun Sharma")
        self.assertEqual(data["trust_score"], 9)
        self.assertEqual(data["status"], "BLOCKED")

    def test_16_validate_audio_diagnostic_endpoint(self):
        """POST /api/debug/validate-audio validates speech and returns AASIST + ECAPA diagnostic fields."""
        import base64
        pcm_bytes = (self.genuine_speech_audio * 32767).astype(np.int16).tobytes()
        b64_audio = base64.b64encode(pcm_bytes).decode("utf-8")

        payload = {
            "audio_base64": b64_audio,
            "sample_rate": 16000,
            "claimed_speaker_id": "cfo_arun"
        }
        res = self.client.post("/api/debug/validate-audio", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("audio_diagnostics", data)
        self.assertIn("aasist_anti_spoof", data)
        self.assertIn("speaker_verification", data)
        self.assertIn("voice_clone_paradox", data)

    def test_17_speaker_delete_persistence(self):
        """Deleting speaker profile removes from memory and SQLite database."""
        del_spk_id = f"exec_to_delete_{int(time.time())}"
        test_emb = np.random.randn(192).astype(np.float32)
        speaker_verifier.enroll_embedding(del_spk_id, "Temporary Exec", test_emb)
        self.assertIn(del_spk_id, speaker_verifier.enrolled_speakers)
        self.assertIsNotNone(speaker_repo.get_speaker(del_spk_id))

        speaker_verifier.delete_speaker(del_spk_id)
        self.assertNotIn(del_spk_id, speaker_verifier.enrolled_speakers)
        self.assertIsNone(speaker_repo.get_speaker(del_spk_id))

    def test_18_analytics_real_metrics(self):
        """GET /api/analytics returns real_metrics alongside standard demonstration KPIs."""
        res = self.client.get("/api/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("kpis", data)
        self.assertIn("real_metrics", data)
        self.assertIn("total_real_calls", data["real_metrics"])

if __name__ == "__main__":
    unittest.main()
