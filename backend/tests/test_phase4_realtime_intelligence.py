import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import time

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.transcription import TranscriptionService, transcription_service
from backend.intelligence.conversation import conversation_intelligence
from backend.intelligence.context import context_engine, empty_session_context
from backend.trust.scoring import trust_engine
from backend.services.live_semantics import append_transcript, incremental_asr, apply_context, maybe_create_incidents, init_session_fields
from backend.services.firebase_sync import firebase_status
from backend.audio.stream_processor import stream_processor, CallAudioBuffer
from backend.database.db import init_db
from backend.database.repositories import call_repo, incident_repo


class TestPhase4RealtimeIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_whisper_empty_and_silence(self):
        svc = TranscriptionService()
        empty = svc.transcribe_audio(np.zeros(0, dtype=np.float32))
        self.assertEqual(empty["status"], "NO_AUDIO")
        silent = svc.transcribe_audio(np.zeros(16000, dtype=np.float32))
        self.assertEqual(silent["status"], "NO_SPEECH")
        self.assertEqual(silent["text"], "")

    def test_whisper_mock_output_schema(self):
        svc = TranscriptionService()
        fake_seg = MagicMock()
        fake_seg.text = "please transfer the money immediately"
        fake_seg.start = 0.0
        fake_seg.end = 1.2
        info = MagicMock()
        info.language = "en"
        model = MagicMock()
        model.transcribe.return_value = ([fake_seg], info)
        svc._model = model
        svc._load_error = None
        audio = (np.sin(2 * np.pi * 220 * np.linspace(0, 2, 32000)) * 0.3).astype(np.float32)
        res = svc.transcribe_audio(audio)
        self.assertEqual(res["status"], "OK")
        self.assertIn("transfer", res["text"].lower())
        self.assertEqual(res["model"], "faster-whisper")
        self.assertNotIn("Hello this is the CFO", res["text"])

    def test_whisper_unavailable(self):
        svc = TranscriptionService()
        svc._model = None
        with patch.object(svc, "load_model", side_effect=RuntimeError("no ctranslate2")):
            audio = (np.sin(2 * np.pi * 220 * np.linspace(0, 2, 32000)) * 0.3).astype(np.float32)
            res = svc.transcribe_audio(audio)
        self.assertEqual(res["status"], "WHISPER_UNAVAILABLE")
        self.assertEqual(res["text"], "")

    def test_transcript_dedupe(self):
        a = append_transcript("please transfer", "transfer the funds immediately")
        self.assertIn("immediately", a)
        self.assertEqual(append_transcript("hello world", "hello world"), "hello world")

    def test_gemini_empty_and_structured(self):
        empty = conversation_intelligence.analyze_transcript("  ")
        self.assertEqual(empty["status"], "EMPTY_TRANSCRIPT")
        threat = conversation_intelligence.analyze_transcript(
            "Hi this is the CFO. Transfer 25 lakh immediately. Do not tell anyone. Send the OTP."
        )
        self.assertTrue(threat["authority_impersonation"])
        self.assertTrue(threat["financial_request"])
        self.assertTrue(threat["credential_request"])
        self.assertNotEqual(threat["recommended_action"], "BLOCK")

    def test_gemini_api_failure_falls_back(self):
        with patch.object(conversation_intelligence, "api_key", "fake-key"):
            with patch.object(conversation_intelligence, "_analyze_gemini", return_value=None):
                res = conversation_intelligence.analyze_transcript("please transfer funds now urgently")
        self.assertTrue(res["available"])
        self.assertIn("risk_score", res)

    def test_context_not_hardcoded(self):
        empty = empty_session_context()
        self.assertIsNone(empty["caller_number"])
        self.assertIsNone(empty["transaction_amount"])
        caller = context_engine.evaluate_caller()
        self.assertEqual(caller["status"], "NOT_PROVIDED")
        txn = context_engine.evaluate_transaction()
        self.assertEqual(txn["status"], "NOT_PROVIDED")

    def test_context_api(self):
        call_id = f"VS-LIVE-CTX-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000)
        res = self.client.post(f"/api/calls/{call_id}/context", json={
            "caller_number": "+910000000000",
            "claimed_identity": "cfo_arun",
            "transaction_amount": 2500000,
            "transaction_currency": "INR",
            "transaction_type": "bank_transfer",
            "beneficiary": "new_account",
            "source": "DEMO_CONTEXT",
        })
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["label"], "DEMO_CONTEXT")
        self.assertEqual(body["session"]["transaction_amount"], 2500000)
        stream_processor.stop_call_stream(call_id)

    def test_trust_inconclusive_and_paradox(self):
        missing = trust_engine.fuse_live_signals(
            aasist={"status": "NOT_ENOUGH_AUDIO", "prediction": "INCONCLUSIVE"},
            ecapa={"status": "INCONCLUSIVE"},
            speech_detected=True,
        )
        self.assertNotEqual(missing.get("recommended_action"), "BLOCK")
        paradox = trust_engine.fuse_live_signals(
            aasist={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.9},
            ecapa={"status": "MATCH", "similarity_pct": 94.0},
            possible_voice_clone=True,
        )
        self.assertTrue(paradox["possible_voice_clone"])
        self.assertEqual(paradox["recommended_action"], "BLOCK")
        self.assertLessEqual(paradox["trust_score"], 9)

    def test_incremental_asr_on_buffer(self):
        buf = CallAudioBuffer("VS-LIVE-ASR", input_sample_rate=16000)
        init_session_fields(buf)
        buf.continuous_16k = (np.sin(2 * np.pi * 180 * np.linspace(0, 3, 48000)) * 0.4).astype(np.float32)
        with patch("backend.services.live_semantics.transcription_service.transcribe_audio", return_value={
            "text": "please confirm the payment",
            "language": "en",
            "status": "OK",
            "inference_ms": 12,
            "model": "faster-whisper",
            "duration": 3.0,
            "segments": [],
        }):
            out = incremental_asr(buf)
        self.assertIsNotNone(out)
        self.assertEqual(out["text"], "please confirm the payment")
        second = incremental_asr(buf)
        self.assertIsNone(second)

    def test_incident_on_clone_paradox(self):
        buf = CallAudioBuffer("VS-LIVE-INC", input_sample_rate=16000)
        init_session_fields(buf)
        buf.last_fused_trust = {"trust_score": 9, "recommended_action": "BLOCK"}
        created = maybe_create_incidents(
            buf,
            {"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.88, "genuine_probability": 0.12, "model": "AASIST", "device": "cpu", "inference_ms": 10},
            {"status": "MATCH", "similarity_pct": 91, "threshold": 0.8, "display_name": "CFO"},
        )
        self.assertTrue(created)
        self.assertEqual(created[0]["type"], "VOICE_CLONE_IMPERSONATION")
        again = maybe_create_incidents(buf, {"status": "OK", "prediction": "SPOOF"}, {"status": "MATCH"})
        self.assertEqual(again, [])

    def test_firebase_unconfigured(self):
        status = firebase_status()
        self.assertIn(status["status"], ("NOT_CONFIGURED", "FIREBASE_UNAVAILABLE", "OK"))

    def test_websocket_standardized_events(self):
        call_id = f"VS-LIVE-WS4-{int(time.time())}"
        with self.client.websocket_connect(f"/ws/call/{call_id}") as ws:
            init_msg = ws.receive_json()
            self.assertEqual(init_msg["type"], "CONNECTION_ESTABLISHED")
            ws.send_json({"type": "START_AUDIO_STREAM", "sample_rate": 16000, "channels": 1})
            started = ws.receive_json()
            self.assertEqual(started["type"], "AUDIO_STREAM_STARTED")
            session = ws.receive_json()
            self.assertEqual(session["type"], "SESSION_STARTED")
            t = np.linspace(0, 1.5, 24000)
            tone = (np.sin(2 * np.pi * 300 * t) * 15000).astype(np.int16)
            ws.send_bytes(tone.tobytes())
            analysis = ws.receive_json()
            self.assertEqual(analysis["type"], "AUDIO_ANALYSIS")
            types = {analysis["type"]}
            for _ in range(5):
                types.add(ws.receive_json()["type"])
            self.assertIn("AUDIO_STATUS", types)
            self.assertIn("AASIST_UPDATE", types)
            self.assertIn("ECAPA_UPDATE", types)
            self.assertIn("TRUST_UPDATE", types)
            ws.send_json({"type": "STOP_AUDIO_STREAM"})
            stopped = ws.receive_json()
            self.assertEqual(stopped["type"], "AUDIO_STREAM_STOPPED")

    def test_calls_mode_real_excludes_demo_ids(self):
        res = self.client.get("/api/calls?mode=REAL")
        self.assertEqual(res.status_code, 200)
        for c in res.json():
            self.assertEqual(c.get("mode"), "REAL")
            self.assertFalse(str(c.get("call_id", "")).startswith("VS-2026-"))


if __name__ == "__main__":
    unittest.main()
