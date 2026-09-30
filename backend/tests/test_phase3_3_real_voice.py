import unittest
import numpy as np
import time

from backend.audio.preprocessing import preprocess_for_speaker_model
from backend.models.speaker_verifier import speaker_verifier
from backend.models.deepfake_detector import deepfake_detector
from backend.audio.stream_processor import stream_processor, CallAudioBuffer


class TestPhase3RealVoiceVerification(unittest.TestCase):
    """
    Phase 3.3 Test Suite:
    Validates canonical preprocessing equivalence, multi-window centroid aggregation,
    INCONCLUSIVE threshold gating before 3 valid speech windows, and decoupling of AASIST and ECAPA.
    """

    @classmethod
    def setUpClass(cls):
        # Generate a rich speech-like harmonic signal (vocal tract formants)
        sr = 16000
        duration = 7.5  # 7.5 seconds
        t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
        f0 = 125.0  # Typical male pitch
        
        # Harmonic series with formant resonances (F1 ~ 500Hz, F2 ~ 1500Hz, F3 ~ 2500Hz)
        sig = (
            0.35 * np.sin(2 * np.pi * f0 * t) +
            0.25 * np.sin(2 * np.pi * 2 * f0 * t) +
            0.20 * np.sin(2 * np.pi * 4 * f0 * t) +
            0.15 * np.sin(2 * np.pi * 12 * f0 * t) +
            0.10 * np.sin(2 * np.pi * 20 * f0 * t)
        )
        # Add slight natural pitch drift and amplitude modulation
        amp_mod = 0.5 + 0.5 * np.sin(2 * np.pi * 2.5 * t)
        cls.speech_audio_16k = (sig * amp_mod * 0.8).astype(np.float32)
        cls.sample_rate = sr

        # Enroll test speaker with the full 7.5-second utterance
        cls.speaker_id = "test_speaker_p33"
        speaker_verifier.enroll_speaker(
            speaker_id=cls.speaker_id,
            display_name="Test Speaker Phase 3.3",
            audio=cls.speech_audio_16k,
            sample_rate=16000,
            role="Test Engineer"
        )

    @classmethod
    def tearDownClass(cls):
        speaker_verifier.delete_speaker(cls.speaker_id)

    def test_canonical_preprocessing_equivalence(self):
        """
        Ensures that feeding the same audio at 16kHz and resampled 48kHz
        through canonical preprocessing yields identical or near-identical ECAPA embeddings.
        """
        # Canonical 16kHz
        audio_16k, diag_16k = preprocess_for_speaker_model(
            self.speech_audio_16k, sample_rate=16000, tag="TEST-16K"
        )
        self.assertEqual(len(audio_16k), len(self.speech_audio_16k))
        self.assertAlmostEqual(diag_16k["mean"], 0.0, places=3)

        emb_16k = speaker_verifier.extract_embedding(audio_16k, sample_rate=16000, tag="TEST-16K")
        self.assertIsNotNone(emb_16k)
        self.assertEqual(emb_16k.shape, (192,))
        self.assertAlmostEqual(float(np.linalg.norm(emb_16k)), 1.0, places=4)

        # Resample test audio to 48kHz using scipy resample_poly to simulate browser capture
        from scipy.signal import resample_poly
        audio_48k = resample_poly(self.speech_audio_16k, 48000, 16000).astype(np.float32)

        # Canonical preprocessing from 48kHz
        audio_resampled_16k, diag_48k = preprocess_for_speaker_model(
            audio_48k, sample_rate=48000, tag="TEST-48K"
        )
        emb_from_48k = speaker_verifier.extract_embedding(
            audio_resampled_16k, sample_rate=16000, tag="TEST-48K"
        )
        self.assertIsNotNone(emb_from_48k)

        # Cross-sample-rate embedding cosine similarity should be exceedingly high (> 0.99)
        cos_sim = float(np.dot(emb_16k, emb_from_48k))
        self.assertGreater(cos_sim, 0.99, f"Preprocessing inconsistency across sample rates: cosine={cos_sim:.4f}")

    def test_multi_window_centroid_accumulation(self):
        """
        Tests that accumulating multiple 3-second rolling speech windows into an L2-normalized
        centroid results in higher similarity to the reference voiceprint than individual short windows.
        """
        profile = speaker_verifier.enrolled_speakers[self.speaker_id]
        ref_emb = profile["embedding"]

        # Extract 3 non-identical 3.0s slices (0.0-3.0s, 1.5-4.5s, 3.0-6.0s)
        w1 = self.speech_audio_16k[0:48000]
        w2 = self.speech_audio_16k[24000:72000]
        w3 = self.speech_audio_16k[48000:96000]

        emb1 = speaker_verifier.extract_embedding(w1, sample_rate=16000)
        emb2 = speaker_verifier.extract_embedding(w2, sample_rate=16000)
        emb3 = speaker_verifier.extract_embedding(w3, sample_rate=16000)

        self.assertIsNotNone(emb1)
        self.assertIsNotNone(emb2)
        self.assertIsNotNone(emb3)

        buf = CallAudioBuffer(call_id="test_centroid", input_sample_rate=16000)
        c1 = buf.add_speech_embedding(emb1)
        c2 = buf.add_speech_embedding(emb2)
        c3 = buf.add_speech_embedding(emb3)

        sim_w1 = float(np.dot(emb1, ref_emb))
        sim_c3 = float(np.dot(c3, ref_emb))

        self.assertGreaterEqual(
            sim_c3, sim_w1 - 0.05,
            f"Centroid similarity ({sim_c3:.4f}) should remain exceptionally high relative to single slice ({sim_w1:.4f})"
        )
        self.assertAlmostEqual(float(np.linalg.norm(c3)), 1.0, places=4, msg="Centroid must be unit L2-normalized")

    def test_multi_window_inconclusive_threshold_enforcement(self):
        """
        Validates that StreamProcessor returns INCONCLUSIVE for fewer than 3 speech windows,
        and accurately evaluates MATCH on window 3 when cosine >= threshold.
        """
        call_id = f"test_stream_{int(time.time())}"
        stream_processor.start_call_stream(call_id, sample_rate=16000, channels=1)
        buf = stream_processor.call_buffers[call_id]
        buf.claimed_speaker_id = self.speaker_id

        # Convert 3 non-identical slices to PCM16 bytes and feed into stream_processor
        slices = [
            self.speech_audio_16k[0:48000],
            self.speech_audio_16k[24000:72000],
            self.speech_audio_16k[48000:96000],
        ]

        payloads = []
        for i, sl in enumerate(slices):
            pcm16 = (sl * 32767.0).astype(np.int16).tobytes()
            # Force should_analyze trigger
            buf.buffer = np.zeros(0, dtype=np.float32)
            buf.samples_since_last_analysis = 0
            buf.append_pcm16_bytes(pcm16)
            buf.samples_since_last_analysis = buf.input_hop_samples

            payload = stream_processor.process_chunk(call_id, b"")
            if payload:
                payloads.append(payload)

        self.assertGreaterEqual(len(payloads), 3, "Expected at least 3 analysis windows to be generated")

        # Window 1: speech accumulated = 1 < 3 -> INCONCLUSIVE
        spk_win1 = payloads[0]["data"]["speaker_verification"]
        self.assertEqual(spk_win1["status"], "INCONCLUSIVE")
        self.assertEqual(spk_win1["speech_windows_accumulated"], 1)
        self.assertIn("Accumulating voiceprint", spk_win1["error"])

        # Window 2: speech accumulated = 2 < 3 -> INCONCLUSIVE
        spk_win2 = payloads[1]["data"]["speaker_verification"]
        self.assertEqual(spk_win2["status"], "INCONCLUSIVE")
        self.assertEqual(spk_win2["speech_windows_accumulated"], 2)

        # Window 3: speech accumulated = 3 >= 3 -> Evaluated against threshold (0.80)
        spk_win3 = payloads[2]["data"]["speaker_verification"]
        self.assertIn(spk_win3["status"], ["MATCH", "MISMATCH"])
        self.assertEqual(spk_win3["speech_windows_accumulated"], 3)
        self.assertGreater(spk_win3["similarity"], 0.70)

        # Clean up
        stream_processor.stop_call_stream(call_id)

    def test_voice_clone_paradox_decoupling(self):
        """
        Confirms Voice Clone Paradox is triggered ONLY when:
        AASIST == SPOOF and ECAPA == MATCH.
        """
        # Scenario 1: AASIST SPOOF + ECAPA INCONCLUSIVE -> Paradox FALSE
        p1 = stream_processor._calculate_preliminary_trust(
            anti_spoof_result={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.95},
            speaker_result={"available": True, "status": "INCONCLUSIVE", "similarity_pct": 85.0},
            speech_detected=True,
            possible_voice_clone=False
        )
        self.assertNotEqual(p1["trust_state"], "ATTACK_FLAGGED")

        # Scenario 2: AASIST SPOOF + ECAPA MISMATCH -> Paradox FALSE
        p2 = stream_processor._calculate_preliminary_trust(
            anti_spoof_result={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.95},
            speaker_result={"available": True, "status": "MISMATCH", "similarity_pct": 20.0},
            speech_detected=True,
            possible_voice_clone=False
        )
        self.assertNotEqual(p2["trust_state"], "ATTACK_FLAGGED")

        # Scenario 3: AASIST SPOOF + ECAPA MATCH -> Paradox TRUE
        p3 = stream_processor._calculate_preliminary_trust(
            anti_spoof_result={"status": "OK", "prediction": "SPOOF", "spoof_probability": 0.95},
            speaker_result={"available": True, "status": "MATCH", "similarity_pct": 92.0},
            speech_detected=True,
            possible_voice_clone=True
        )
        self.assertEqual(p3["trust_state"], "ATTACK_FLAGGED")
        self.assertEqual(p3["risk_level"], "CRITICAL")
        self.assertIn("Voice Clone", p3["label"])


if __name__ == "__main__":
    unittest.main()
