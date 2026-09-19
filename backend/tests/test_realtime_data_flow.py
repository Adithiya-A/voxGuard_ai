import unittest
import numpy as np
import time
from fastapi.testclient import TestClient

from backend.main import app
from backend.audio.stream_processor import stream_processor

class TestRealtimeDataFlow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_dynamic_live_session_isolation(self):
        """Test that dynamic VS-LIVE-... call IDs are isolated and do not reuse mock data."""
        session_id_1 = f"VS-LIVE-{int(time.time() * 1000)}"
        session_id_2 = f"VS-LIVE-{int(time.time() * 1000) + 1000}"

        # 1. Start session 1
        buf1 = stream_processor.start_call_stream(session_id_1, sample_rate=16000, channels=1)
        self.assertIsNotNone(buf1)
        self.assertEqual(buf1.call_id, session_id_1)

        # Feed 1.5s of simulated audio
        samples = (np.sin(2 * np.pi * 440 * np.linspace(0, 1.5, 24000)) * 16000).astype(np.int16)
        payload1 = stream_processor.process_chunk(session_id_1, samples.tobytes())
        self.assertIsNotNone(payload1)
        self.assertEqual(payload1["call_id"], session_id_1)
        self.assertTrue(payload1["data"]["speech_detected"])

        # Stop session 1
        summary1 = stream_processor.stop_call_stream(session_id_1)
        self.assertIsNotNone(summary1)
        self.assertEqual(summary1["call_id"], session_id_1)
        self.assertEqual(summary1["total_windows"], 1)
        self.assertEqual(summary1["speech_windows"], 1)
        self.assertNotIn(session_id_1, stream_processor.call_buffers)

        # 2. Start session 2 - must be completely clean and isolated
        buf2 = stream_processor.start_call_stream(session_id_2, sample_rate=16000, channels=1)
        self.assertIsNotNone(buf2)
        self.assertEqual(buf2.call_id, session_id_2)
        self.assertEqual(buf2.window_count, 0)
        self.assertEqual(buf2.speech_window_count, 0)
        self.assertEqual(len(buf2.buffer), 0)

        # Stop session 2
        summary2 = stream_processor.stop_call_stream(session_id_2)
        self.assertIsNotNone(summary2)
        self.assertEqual(summary2["call_id"], session_id_2)
        self.assertEqual(summary2["total_windows"], 0)

    def test_duplicate_initialization_prevented(self):
        """Calling start_call_stream multiple times for the same session ID reuses the active buffer."""
        session_id = f"VS-LIVE-DUP-{int(time.time())}"
        buf_first = stream_processor.start_call_stream(session_id, sample_rate=48000, channels=1)
        buf_second = stream_processor.start_call_stream(session_id, sample_rate=48000, channels=1)

        self.assertIs(buf_first, buf_second, "Second initialization should return the exact existing buffer instance")
        stream_processor.stop_call_stream(session_id)

    def test_websocket_live_stream_lifecycle(self):
        """Test full WebSocket connection, START, audio stream, analysis, and STOP lifecycle."""
        call_id = f"VS-LIVE-WS-{int(time.time())}"
        with self.client.websocket_connect(f"/ws/call/{call_id}") as ws:
            # 1. Connection established
            init_msg = ws.receive_json()
            self.assertEqual(init_msg["type"], "CONNECTION_ESTABLISHED")
            self.assertEqual(init_msg["call_id"], call_id)

            # 2. Send START_AUDIO_STREAM
            ws.send_json({
                "type": "START_AUDIO_STREAM",
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm_s16le"
            })
            started_msg = ws.receive_json()
            self.assertEqual(started_msg["type"], "AUDIO_STREAM_STARTED")
            self.assertEqual(started_msg["call_id"], call_id)

            # 3. Stream 1.5s audio chunk
            t = np.linspace(0, 1.5, 24000)
            tone = (np.sin(2 * np.pi * 300 * t) * 15000).astype(np.int16)
            ws.send_bytes(tone.tobytes())

            analysis_msg = ws.receive_json()
            self.assertEqual(analysis_msg["type"], "AUDIO_ANALYSIS")
            self.assertEqual(analysis_msg["call_id"], call_id)
            self.assertIn("speech_detected", analysis_msg["data"])

            # 4. Send STOP_AUDIO_STREAM
            ws.send_json({"type": "STOP_AUDIO_STREAM"})
            stopped_msg = ws.receive_json()
            self.assertEqual(stopped_msg["type"], "AUDIO_STREAM_STOPPED")
            self.assertEqual(stopped_msg["call_id"], call_id)
            self.assertGreaterEqual(stopped_msg["summary"]["total_windows"], 1)

if __name__ == "__main__":
    unittest.main()
