import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import time

from backend.models.deepfake_detector import deepfake_detector, DeepfakeDetector
from backend.audio.stream_processor import stream_processor

class TestPhase2DeepfakeDetector(unittest.TestCase):
    def setUp(self):
        self.sr = 16000
        # Generate 3-second 16kHz test tone
        t = np.linspace(0, 3.0, int(self.sr * 3.0), endpoint=False)
        self.test_audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

    # Test 1 — Empty audio
    def test_empty_audio(self):
        res = deepfake_detector.analyze(np.zeros(0, dtype=np.float32), sample_rate=16000)
        self.assertEqual(res["status"], "NO_AUDIO")
        self.assertEqual(res["prediction"], "INCONCLUSIVE")
        self.assertIsNone(res["spoof_probability"])
        self.assertIsNone(res["genuine_probability"])
        self.assertIsNone(res["ai_probability"])

    # Test 2 — Silence bypass
    def test_silence_bypass(self):
        res = deepfake_detector.analyze(self.test_audio, sample_rate=16000, speech_detected=False)
        self.assertEqual(res["status"], "NO_SPEECH")
        self.assertEqual(res["prediction"], "INCONCLUSIVE")
        self.assertIsNone(res["spoof_probability"])
        self.assertIsNone(res["genuine_probability"])
        self.assertEqual(res["inference_ms"], 0.0)

    # Test 3 — Model loading
    def test_model_loading(self):
        deepfake_detector.load_model()
        self.assertTrue(deepfake_detector.is_loaded())
        self.assertIsNotNone(deepfake_detector.model)
        self.assertIn(deepfake_detector.device, ["cpu", "cuda"])

    # Test 4 — Model reuse (Caching)
    def test_model_reuse(self):
        deepfake_detector.load_model()
        initial_model_obj = deepfake_detector.model

        # Perform two inferences
        res1 = deepfake_detector.analyze(self.test_audio, sample_rate=16000, speech_detected=True)
        res2 = deepfake_detector.analyze(self.test_audio, sample_rate=16000, speech_detected=True)

        self.assertIs(deepfake_detector.model, initial_model_obj, "Model object must remain cached in memory")
        self.assertEqual(res1["status"], "OK")
        self.assertEqual(res2["status"], "OK")

    # Test 5 — Output schema compliance
    def test_output_schema(self):
        res = deepfake_detector.analyze(self.test_audio, sample_rate=16000, speech_detected=True)
        self.assertEqual(res["status"], "OK")
        self.assertIn(res["prediction"], ["SPOOF", "BONAFIDE", "LIKELY_GENUINE"])
        self.assertIsInstance(res["spoof_probability"], float)
        self.assertIsInstance(res["genuine_probability"], float)
        self.assertGreaterEqual(res["spoof_probability"], 0.0)
        self.assertLessEqual(res["spoof_probability"], 1.0)
        self.assertGreaterEqual(res["genuine_probability"], 0.0)
        self.assertLessEqual(res["genuine_probability"], 1.0)
        self.assertAlmostEqual(res["spoof_probability"] + res["genuine_probability"], 1.0, places=2)
        self.assertEqual(res["model"], "AASIST")
        self.assertEqual(res["model_version"], "AASIST-ASVspoof2019-LA")
        self.assertIn(res["device"], ["cpu", "cuda"])
        self.assertGreater(res["inference_ms"], 0.0)
        self.assertIsNotNone(res["score"])

    # Test 6 — Model error handling
    def test_model_error_handling(self):
        detector = DeepfakeDetector()
        # Mock model forward pass raising an unhandled exception
        mock_model = MagicMock()
        mock_model.side_effect = RuntimeError("Simulated Tensor Core OOM")
        detector.model = mock_model
        detector.model_loaded = True

        res = detector.analyze(self.test_audio, sample_rate=16000, speech_detected=True)
        self.assertEqual(res["status"], "MODEL_ERROR")
        self.assertEqual(res["prediction"], "INCONCLUSIVE")
        self.assertIsNone(res["spoof_probability"])
        self.assertIsNone(res["genuine_probability"])
        self.assertIn("Simulated Tensor Core OOM", res["error"])

    # Test 7 — Resampling from 48kHz to 16kHz
    def test_audio_resampling_48k(self):
        t_48k = np.linspace(0, 3.0, int(48000 * 3.0), endpoint=False)
        audio_48k = (np.sin(2 * np.pi * 440 * t_48k) * 0.5).astype(np.float32)

        res = deepfake_detector.analyze(audio_48k, sample_rate=48000, speech_detected=True)
        self.assertEqual(res["status"], "OK")
        self.assertIsNotNone(res["spoof_probability"])

    # Test 8 — StreamProcessor integration with latency_ms and anti_spoof
    def test_stream_processor_integration(self):
        call_id = f"TEST-AASIST-{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, channels=1)

        # 1.5s audio chunk (PCM16)
        samples_pcm16 = (self.test_audio[:24000] * 32767).astype(np.int16)
        analysis = stream_processor.process_chunk(call_id, samples_pcm16.tobytes())

        self.assertIsNotNone(analysis)
        data = analysis["data"]
        self.assertIn("voice_authenticity", data)
        self.assertIn("anti_spoof", data["voice_authenticity"])
        anti_spoof = data["voice_authenticity"]["anti_spoof"]
        self.assertEqual(anti_spoof["model"], "AASIST")
        self.assertEqual(anti_spoof["status"], "OK")

        # Check latency_ms
        self.assertIn("latency_ms", data)
        self.assertIn("anti_spoof", data["latency_ms"])
        self.assertGreater(data["latency_ms"]["anti_spoof"], 0.0)

        stream_processor.stop_call_stream(call_id)

if __name__ == "__main__":
    unittest.main()
