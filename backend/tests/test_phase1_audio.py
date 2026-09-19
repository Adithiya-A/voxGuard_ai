import unittest
import numpy as np
import json
import time

from backend.audio.vad import dsp_vad, detect_voice_activity
from backend.models.prosody import prosody_analyzer
from backend.audio.stream_processor import AudioStreamProcessor, CallAudioBuffer
from backend.trust.scoring import trust_engine
from backend.main import app
from fastapi.testclient import TestClient

class TestPhase1AudioPipeline(unittest.TestCase):
    def setUp(self):
        self.processor = AudioStreamProcessor()
        self.client = TestClient(app)

    # ==================== 1. AUDIO BUFFERING & RESAMPLING TESTS ====================
    def test_pcm16_decoding_and_resampling(self):
        """
        Verify that 48kHz PCM16 audio is decoded, normalized to [-1.0, 1.0],
        and accurately resampled to 16kHz.
        """
        buf = CallAudioBuffer(
            call_id="TEST-CALL-01",
            input_sample_rate=48000,
            channels=1,
            target_sample_rate=16000,
            window_seconds=3.0,
            hop_seconds=1.0
        )

        # Generate 1.0 second of 440 Hz tone at 48kHz
        t = np.linspace(0, 1.0, 48000, endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        int16_tone = (tone * 32767).astype(np.int16)
        raw_bytes = int16_tone.tobytes()

        # Ingest into buffer
        samples_added = buf.append_pcm16_bytes(raw_bytes)
        self.assertEqual(samples_added, 16000) # 48k -> 16k is 16,000 samples
        self.assertAlmostEqual(buf.buffer_duration_seconds, 1.0, places=2)

    def test_3_second_window_creation(self):
        """
        Verify that feeding 3+ seconds of audio creates a full 3-second (48,000 sample) window.
        """
        buf = CallAudioBuffer(
            call_id="TEST-CALL-02",
            input_sample_rate=16000,
            channels=1,
            target_sample_rate=16000,
            window_seconds=3.0,
            hop_seconds=1.0
        )

        # Feed three 1-second chunks
        for _ in range(3):
            chunk = np.zeros(16000, dtype=np.int16).tobytes()
            buf.append_pcm16_bytes(chunk)

        self.assertTrue(buf.should_analyze())
        window = buf.get_analysis_window()
        self.assertEqual(len(window), 48000) # 3.0s * 16000Hz = 48000 samples

    def test_empty_and_short_audio(self):
        """
        Verify that empty or extremely small bytes do not crash the buffer or processors.
        """
        buf = CallAudioBuffer(call_id="TEST-CALL-EMPTY")
        samples = buf.append_pcm16_bytes(b"")
        self.assertEqual(samples, 0)
        self.assertFalse(buf.should_analyze())

        vad_res = dsp_vad.analyze(np.zeros(0, dtype=np.float32))
        self.assertFalse(vad_res["speech_detected"])
        self.assertEqual(vad_res["energy"], 0.0)

        pros_res = prosody_analyzer.analyze(np.zeros(0, dtype=np.float32))
        self.assertFalse(pros_res["available"])

    # ==================== 2. VAD TESTS ====================
    def test_vad_silence(self):
        """
        Verify that digital silence produces no speech detected and near-zero probability.
        """
        silence = np.zeros(16000, dtype=np.float32)
        res = dsp_vad.analyze(silence, sample_rate=16000)
        self.assertFalse(res["speech_detected"])
        self.assertLess(res["speech_probability"], 0.15)
        self.assertEqual(res["vad_type"], "DSP VAD")

    def test_vad_simulated_speech(self):
        """
        Verify that a voiced harmonic tone with speech-like energy is flagged as speech.
        """
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        # Fundamental (150Hz) + harmonics (300Hz, 450Hz) typical of human male voice
        vocal = 0.3 * np.sin(2 * np.pi * 150 * t) + 0.15 * np.sin(2 * np.pi * 300 * t)
        vocal = vocal.astype(np.float32)

        res = dsp_vad.analyze(vocal, sample_rate=16000)
        self.assertTrue(res["speech_detected"])
        self.assertGreater(res["speech_probability"], 0.6)
        self.assertGreater(res["rms"], 0.01)

    def test_vad_noise(self):
        """
        Verify VAD behavior on low-level background hiss.
        """
        np.random.seed(42)
        noise = (np.random.normal(0, 0.002, 16000)).astype(np.float32)
        res = dsp_vad.analyze(noise, sample_rate=16000)
        self.assertFalse(res["speech_detected"])

    # ==================== 3. REAL PROSODY TESTS ====================
    def test_prosody_genuine_f0_pitch_extraction(self):
        """
        Verify that F0 autocorrelation extracts the true fundamental frequency
        and does NOT return a hardcoded 132.4 Hz.
        """
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        # 220 Hz clean harmonic tone (A3 note)
        tone_220 = (0.4 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        res = prosody_analyzer.analyze(tone_220, sample_rate=16000)
        self.assertTrue(res["available"])
        self.assertIsNotNone(res["fundamental_f0_hz"])
        # Should be within +/- 5 Hz of 220 Hz
        self.assertAlmostEqual(res["fundamental_f0_hz"], 220.0, delta=5.0)
        self.assertNotEqual(res["fundamental_f0_hz"], 132.4) # Must NOT be the old fake constant

    def test_prosody_unvoiced_silence(self):
        """
        Verify that silence returns available=False rather than fabricating an F0.
        """
        silence = np.zeros(16000, dtype=np.float32)
        res = prosody_analyzer.analyze(silence, sample_rate=16000)
        self.assertFalse(res["available"])
        self.assertIn("insufficient voiced samples", res["reason"])
        self.assertIsNone(res["fundamental_f0_hz"])

    # ==================== 4. STREAM PROCESSOR SPECTRAL FEATURES ====================
    def test_spectral_features_extraction(self):
        """
        Verify that spectral features are computed directly from audio window:
        centroid, flatness, bandwidth, rolloff, and HF energy.
        """
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        # 1000 Hz pure sine wave
        audio = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)

        features = self.processor._extract_spectral_features(audio, sample_rate=16000)
        self.assertIn("spectral_centroid_hz", features)
        self.assertIn("spectral_flatness", features)
        self.assertIn("high_frequency_energy", features)
        self.assertIn("zcr", features)

        # Centroid for 1000Hz pure tone should be centered near 1000 Hz
        self.assertAlmostEqual(features["spectral_centroid_hz"], 1000.0, delta=50.0)
        # Flatness for pure tone should be very low (< 0.05)
        self.assertLess(features["spectral_flatness"], 0.05)

    # ==================== 5. PRELIMINARY TRUST SCORING ====================
    def test_preliminary_trust_structure(self):
        """
        Verify that Phase 1 trust score is labeled as Preliminary
        and marks unready signals explicitly.
        """
        trust = self.processor._calculate_preliminary_trust(
            voice_ai_probability=15.0,
            prosody_anomaly=20.0,
            speech_detected=True
        )
        self.assertIn("Preliminary", trust["label"])
        self.assertEqual(trust["signal_status"]["voice_authenticity"], "available")
        self.assertEqual(trust["signal_status"]["prosody"], "available")
        self.assertEqual(trust["signal_status"]["speaker_verification"], "not_ready")
        self.assertEqual(trust["signal_status"]["conversation_risk"], "not_ready")
        self.assertGreater(trust["score"], 70)

    # ==================== 6. WEBSOCKET INTEGRATION TEST ====================
    def test_websocket_binary_streaming(self):
        """
        Verify end-to-end WebSocket flow:
        - connect
        - START_AUDIO_STREAM
        - send binary PCM16 audio chunks
        - receive AUDIO_ANALYSIS
        - STOP_AUDIO_STREAM
        - disconnect cleanly
        """
        call_id = f"WS-TEST-{int(time.time())}"
        with self.client.websocket_connect(f"/ws/call/{call_id}") as websocket:
            # 1. Connection established message
            init_msg = websocket.receive_json()
            self.assertEqual(init_msg["type"], "CONNECTION_ESTABLISHED")

            # 2. Send START_AUDIO_STREAM JSON handshake
            websocket.send_json({
                "type": "START_AUDIO_STREAM",
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm_s16le"
            })
            ack_msg = websocket.receive_json()
            self.assertEqual(ack_msg["type"], "AUDIO_STREAM_STARTED")
            self.assertEqual(ack_msg["sample_rate"], 16000)

            # 3. Stream 1.2 seconds of voiced audio as binary PCM16 (triggers initial analysis)
            t = np.linspace(0, 1.2, int(16000 * 1.2), endpoint=False)
            audio = (0.4 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
            pcm16_bytes = (audio * 32767).astype(np.int16).tobytes()

            websocket.send_bytes(pcm16_bytes)

            # Receive real AUDIO_ANALYSIS message
            analysis_msg = websocket.receive_json()
            self.assertEqual(analysis_msg["type"], "AUDIO_ANALYSIS")
            self.assertEqual(analysis_msg["call_id"], call_id)
            self.assertIn("data", analysis_msg)
            self.assertIn("audio", analysis_msg["data"])
            self.assertIn("prosody", analysis_msg["data"])
            self.assertIn("preliminary_trust", analysis_msg["data"])

            # 4. Stop stream
            websocket.send_json({"type": "STOP_AUDIO_STREAM"})
            stop_msg = websocket.receive_json()
            self.assertEqual(stop_msg["type"], "AUDIO_STREAM_STOPPED")

if __name__ == "__main__":
    unittest.main()
