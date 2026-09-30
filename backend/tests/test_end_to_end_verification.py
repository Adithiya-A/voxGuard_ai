"""
VoxGuard AI — End-to-End Verification Test Suite
Verifies:
1. AASIST result schema
2. ECAPA result schema
3. Voice Clone Paradox (AASIST=SPOOF + ECAPA=MATCH => CRITICAL/BLOCK)
4. INCONCLUSIVE handling (never converts to SPOOF or MISMATCH)
5. Trust Engine deterministic scoring and weighting
6. Incident creation and schema
7. SQLite forensic persistence for calls and timeline
8. Speaker persistence across restarts
9. WebSocket event sequence and contract
10. REAL vs DEMO session isolation
11. Call finalization and summary stats
12. End-to-end real audio execution using actual WAV file
"""

import os
import time
import json
import unittest
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from backend.main import app
from backend.audio.preprocessing import preprocess_for_speaker_model
from backend.models.deepfake_detector import deepfake_detector
from backend.models.speaker_verifier import speaker_verifier
from backend.models.prosody import prosody_analyzer
from backend.models.transcription import transcription_service
from backend.intelligence.conversation import conversation_intelligence
from backend.trust.scoring import trust_engine
from backend.database.db import init_db
from backend.database.repositories import call_repo, speaker_repo, incident_repo
from backend.database.models import CallRecord, SpeakerRecord
from backend.audio.stream_processor import stream_processor, CallAudioBuffer
from backend.services.live_semantics import maybe_create_incidents, init_session_fields


class TestEndToEndVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.wav_path = os.path.join(os.path.dirname(__file__), "fixtures", "genuine_speech.wav")

    # 1. AASIST Result Schema
    def test_01_aasist_result_schema(self):
        t = np.linspace(0, 4.0, 64000, endpoint=False, dtype=np.float32)
        audio = (0.3 * np.sin(2 * np.pi * 250 * t)).astype(np.float32)
        res = deepfake_detector.analyze(audio, 16000, speech_detected=True, min_required_samples=24000)
        self.assertIn("status", res)
        self.assertIn("prediction", res)
        self.assertIn("spoof_probability", res)
        self.assertIn("genuine_probability", res)
        self.assertIn("model", res)
        self.assertEqual(res["model"], "AASIST")
        self.assertIn("inference_ms", res)
        self.assertIn(res["prediction"], ("BONAFIDE", "SPOOF", "INCONCLUSIVE"))

    # 2. ECAPA Result Schema
    def test_02_ecapa_result_schema(self):
        t = np.linspace(0, 2.0, 32000, endpoint=False, dtype=np.float32)
        audio = (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
        res = speaker_verifier.verify_speaker(audio, claimed_speaker_id="cfo_arun", sample_rate=16000)
        self.assertIn("status", res)
        self.assertIn("similarity", res)
        self.assertIn("similarity_pct", res)
        self.assertIn("threshold", res)
        self.assertIn("speaker_id", res)
        self.assertIn("embedding_dimension", res)
        self.assertEqual(res["embedding_dimension"], 192)
        self.assertIn(res["status"], ("MATCH", "MISMATCH", "INCONCLUSIVE", "NOT_ENROLLED", "NO_SPEECH"))

    # 3. Voice Clone Paradox (AASIST=SPOOF + ECAPA=MATCH => CRITICAL/BLOCK)
    def test_03_voice_clone_paradox(self):
        res = trust_engine.fuse_live_signals(
            aasist={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.92, "model": "AASIST"},
            ecapa={"status": "MATCH", "similarity_pct": 91.5, "similarity": 0.915, "threshold": 0.8},
            possible_voice_clone=True,
            speech_detected=True,
        )
        self.assertTrue(res["possible_voice_clone"])
        self.assertEqual(res["risk_level"], "CRITICAL")
        self.assertEqual(res["recommended_action"], "BLOCK")
        self.assertLessEqual(res["trust_score"], 9)

    # 4. INCONCLUSIVE Handling (Never converts to SPOOF or MISMATCH)
    def test_04_inconclusive_handling(self):
        # Insufficient speech in AASIST returns INCONCLUSIVE
        short_audio = np.zeros(2000, dtype=np.float32)
        aasist_short = deepfake_detector.analyze(short_audio, 16000, speech_detected=True, min_required_samples=24000)
        self.assertEqual(aasist_short["prediction"], "INCONCLUSIVE")
        self.assertNotEqual(aasist_short["prediction"], "SPOOF")

        # Insufficient speech in ECAPA returns INCONCLUSIVE
        ecapa_short = speaker_verifier.verify_speaker(short_audio, claimed_speaker_id="cfo_arun", sample_rate=16000)
        self.assertEqual(ecapa_short["status"], "INCONCLUSIVE")
        self.assertNotEqual(ecapa_short["status"], "MISMATCH")

        # Fusion on inconclusive signals never blocks
        fused = trust_engine.fuse_live_signals(aasist=aasist_short, ecapa=ecapa_short, speech_detected=True)
        self.assertNotEqual(fused.get("recommended_action"), "BLOCK")
        self.assertFalse(fused.get("possible_voice_clone", False))

    # 5. Trust Engine Weights & Factors
    def test_05_trust_engine_weights_and_factors(self):
        aasist_bonafide = {"status": "OK", "prediction": "BONAFIDE", "spoof_probability": 0.05, "model": "AASIST"}
        ecapa_match = {"status": "MATCH", "similarity_pct": 92.0, "similarity": 0.92, "threshold": 0.8}
        prosody_clean = {"behavior_anomaly": 10.0}
        gemini_safe = {"risk_score": 5.0, "status": "OK"}

        fused = trust_engine.fuse_live_signals(
            aasist=aasist_bonafide,
            ecapa=ecapa_match,
            prosody=prosody_clean,
            gemini=gemini_safe,
            speech_detected=True
        )
        self.assertGreaterEqual(fused["trust_score"], 80)
        self.assertIn("breakdown", fused)
        self.assertIn("contributions", fused)
        self.assertIn("weights", fused)

    # 6. Incident Creation
    def test_06_incident_creation_on_clone_paradox(self):
        cid = "VS-LIVE-TEST-INC"
        call_repo.create_call(call_id=cid)
        buf = CallAudioBuffer(cid, input_sample_rate=16000)
        init_session_fields(buf)
        buf.last_fused_trust = {"trust_score": 8, "recommended_action": "BLOCK"}
        incidents = maybe_create_incidents(
            buf,
            aasist={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.95, "model": "AASIST", "device": "cpu"},
            ecapa={"status": "MATCH", "similarity_pct": 92.0, "display_name": "CFO Arun"},
        )
        self.assertGreaterEqual(len(incidents), 1)
        clone_incs = [i for i in incidents if i["type"] == "VOICE_CLONE_IMPERSONATION"]
        self.assertEqual(len(clone_incs), 1)
        self.assertEqual(clone_incs[0]["severity"], "CRITICAL")
        self.assertEqual(clone_incs[0].get("call_id") or clone_incs[0].get("session_id"), cid)

    # 7. SQLite Persistence for Calls & Timeline
    def test_07_sqlite_persistence_call_and_timeline(self):
        call_id = f"VS-LIVE-TEST-PERSIST-{int(time.time())}"
        rec = CallRecord(
            call_id=call_id,
            source="LIVE_MICROPHONE",
            mode="REAL",
            status="ACTIVE",
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            trust_score=88,
            trust_level="SAFE",
            action="ALLOW",
        )
        call_repo.save_call(rec)
        retrieved = call_repo.get_call(call_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.call_id, call_id)
        self.assertEqual(retrieved.mode, "REAL")

        # Append timeline event
        call_repo.append_timeline_event(call_id, {
            "event_type": "TRUST_UPDATE",
            "timestamp": time.time(),
            "trust_score": 88
        })
        timeline = call_repo.get_timeline(call_id)
        self.assertGreaterEqual(len(timeline), 1)

    # 8. Speaker Persistence Across Restarts
    def test_08_speaker_persistence_across_restarts(self):
        sid = f"test_exec_{int(time.time())}"
        fake_emb = np.random.randn(192).astype(np.float32)
        fake_emb = (fake_emb / np.linalg.norm(fake_emb)).astype(np.float32)
        speaker_verifier.enroll_embedding(
            speaker_id=sid,
            display_name="Test Executive",
            embedding=fake_emb,
            role="VP Engineering"
        )
        self.assertIn(sid, speaker_verifier.enrolled_speakers)

        # Simulate backend restart: re-hydrate from database
        speaker_verifier.enrolled_speakers.clear()
        speaker_verifier.reload_from_database()
        self.assertIn(sid, speaker_verifier.enrolled_speakers)
        reloaded = speaker_verifier.enrolled_speakers[sid]
        self.assertEqual(reloaded["display_name"], "Test Executive")
        self.assertEqual(len(reloaded["embedding"]), 192)

        # Cleanup
        speaker_verifier.delete_speaker(sid)
        self.assertNotIn(sid, speaker_verifier.enrolled_speakers)

    # 9. WebSocket Event Sequence Contract
    def test_09_websocket_event_sequence(self):
        call_id = f"VS-LIVE-SEQ-{int(time.time())}"
        with self.client.websocket_connect(f"/ws/call/{call_id}") as ws:
            # 1. Connection established
            c = ws.receive_json()
            self.assertEqual(c["type"], "CONNECTION_ESTABLISHED")

            # 2. Handshake
            ws.send_json({"type": "START_AUDIO_STREAM", "sample_rate": 16000, "channels": 1})
            s1 = ws.receive_json()
            self.assertEqual(s1["type"], "AUDIO_STREAM_STARTED")
            s2 = ws.receive_json()
            self.assertEqual(s2["type"], "SESSION_STARTED")

            # 3. Stream PCM audio
            t = np.linspace(0, 1.0, 16000)
            tone = (np.sin(2 * np.pi * 350 * t) * 12000).astype(np.int16)
            ws.send_bytes(tone.tobytes())

            # 4. Receive live telemetry events
            analysis = ws.receive_json()
            self.assertEqual(analysis["type"], "AUDIO_ANALYSIS")

            received_types = set()
            for _ in range(5):
                received_types.add(ws.receive_json()["type"])

            self.assertIn("AUDIO_STATUS", received_types)
            self.assertIn("AASIST_UPDATE", received_types)
            self.assertIn("ECAPA_UPDATE", received_types)
            self.assertIn("PROSODY_UPDATE", received_types)
            self.assertIn("TRUST_UPDATE", received_types)

            # 5. Stop stream
            ws.send_json({"type": "STOP_AUDIO_STREAM"})
            stopped = None
            for _ in range(10):
                msg = ws.receive_json()
                if msg.get("type") == "AUDIO_STREAM_STOPPED":
                    stopped = msg
                    break
            self.assertIsNotNone(stopped)
            self.assertEqual(stopped["type"], "AUDIO_STREAM_STOPPED")

    # 10. REAL vs DEMO Isolation
    def test_10_real_demo_isolation(self):
        res_real = self.client.get("/api/calls?mode=REAL")
        self.assertEqual(res_real.status_code, 200)
        real_calls = res_real.json()
        for c in real_calls:
            self.assertEqual(c.get("mode"), "REAL")
            self.assertFalse(str(c.get("call_id")).startswith("VS-2026-"))

        res_demo = self.client.get("/api/calls?mode=DEMO")
        self.assertEqual(res_demo.status_code, 200)
        demo_calls = res_demo.json()
        for c in demo_calls:
            self.assertEqual(c.get("mode"), "DEMO")

    # 11. Call Finalization
    def test_11_call_finalization(self):
        call_id = f"VS-LIVE-FIN-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000)
        t = np.linspace(0, 1.2, 19200)
        tone = (np.sin(2 * np.pi * 300 * t) * 10000).astype(np.int16).tobytes()
        stream_processor.process_chunk(call_id, tone)
        summary = stream_processor.stop_call_stream(call_id)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["call_id"], call_id)
        self.assertIn("duration_seconds", summary)
        self.assertIn("trust_score", summary)
        self.assertIn("action", summary)

    # 12. Real Audio WAV Pipeline Execution
    def test_12_real_audio_wav_pipeline(self):
        self.assertTrue(os.path.exists(self.wav_path), f"WAV fixture not found at {self.wav_path}")
        audio, sr = sf.read(self.wav_path)
        audio_16k, diag = preprocess_for_speaker_model(audio, sr, tag="E2E-TEST")

        # Check diagnostics
        self.assertEqual(diag["sample_rate"], 16000)
        self.assertGreater(diag["duration"], 1.0)
        self.assertGreater(diag["rms"], 0.001)

        # AASIST
        aasist_res = deepfake_detector.analyze(audio_16k, 16000, speech_detected=True, min_required_samples=24000)
        self.assertEqual(aasist_res["status"], "OK")
        self.assertEqual(aasist_res["prediction"], "BONAFIDE")
        self.assertLess(aasist_res["spoof_probability"], 0.5)

        # ECAPA
        ecapa_res = speaker_verifier.verify_speaker(audio_16k, claimed_speaker_id="cfo_arun", sample_rate=16000)
        self.assertEqual(ecapa_res["available"], True)
        self.assertIn(ecapa_res["status"], ("MATCH", "MISMATCH"))

        # Prosody
        prosody_res = prosody_analyzer.analyze(audio_16k, 16000)
        self.assertEqual(prosody_res["available"], True)
        self.assertGreater(prosody_res["fundamental_f0_hz"], 50.0)

        # Whisper
        whisper_res = transcription_service.transcribe_audio(audio_16k, 16000)
        self.assertEqual(whisper_res["status"], "OK")
        self.assertIn("birch canoe", whisper_res["text"].lower())

        # Gemini / Intelligence
        gemini_res = conversation_intelligence.analyze_transcript(whisper_res["text"])
        self.assertIn("risk_score", gemini_res)
        self.assertIn("intent", gemini_res)

        # Trust Engine
        trust_res = trust_engine.fuse_live_signals(
            aasist=aasist_res,
            ecapa=ecapa_res,
            prosody=prosody_res,
            gemini=gemini_res,
            speech_detected=True
        )
        self.assertIn("trust_score", trust_res)
        self.assertIn("risk_level", trust_res)
        self.assertIn("recommended_action", trust_res)
        self.assertFalse(trust_res["possible_voice_clone"])


if __name__ == "__main__":
    unittest.main()
