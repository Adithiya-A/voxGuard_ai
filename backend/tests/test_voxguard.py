# Unit tests for VoxGuard AI core engines
from backend.trust.scoring import trust_engine
from backend.models.deepfake_detector import deepfake_detector
from backend.models.speaker_verification import speaker_verification
from backend.intelligence.conversation import conversation_intelligence
from backend.intelligence.context import context_engine
from backend.blockchain.audit import audit_blockchain

def test_trust_engine_safe():
    # Genuine call: Low voice synthetic risk, high speaker similarity
    result = trust_engine.calculate_trust(
        voice_synthetic_risk=4.0,
        speaker_similarity=96.0,
        prosody_anomaly=8.0,
        conversation_risk=6.0,
        caller_risk=5.0,
        transaction_risk=5.0
    )
    assert result["trust_score"] >= 90
    assert result["risk_level"] == "SAFE"
    assert result["recommended_action"] == "ALLOW"

def test_trust_engine_critical_clone():
    # Attack: High synthetic probability + High speaker similarity (CFO impersonation)
    result = trust_engine.calculate_trust(
        voice_synthetic_risk=87.0,
        speaker_similarity=94.2,
        prosody_anomaly=72.0,
        conversation_risk=91.0,
        caller_risk=85.0,
        transaction_risk=95.0
    )
    assert result["trust_score"] < 30
    assert result["risk_level"] == "CRITICAL"
    assert result["recommended_action"] == "BLOCK_TRANSACTION"

def test_deepfake_detector_clean():
    import numpy as np
    dummy_audio = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000)).astype(np.float32)
    res = deepfake_detector.analyze(dummy_audio, 16000)
    assert "ai_probability" in res
    assert "harmonic_consistency" in res
    assert "spectral_anomaly" in res

def test_speaker_verification():
    import numpy as np
    dummy = np.zeros(16000, dtype=np.float32)
    res = speaker_verification.verify(dummy, claimed_identity="CFO")
    assert res["claimed_identity"] == "CFO"
    assert res["speaker_name"] == "Arun Sharma"
    assert res["speaker_similarity"] > 0

def test_conversation_intelligence_fallback():
    sample_threat = "Hi, this is the CFO. Transfer ₹25 lakh to new account immediately. It is strictly confidential."
    res = conversation_intelligence.analyze_transcript(sample_threat)
    assert res["authority_impersonation"] is True
    assert res["financial_request"] is True
    assert res["urgency"] is True
    assert res["confidentiality_pressure"] is True
    assert res["social_engineering_risk"] > 75

def test_blockchain_sha256_audit():
    event = audit_blockchain.create_event(
        call_id="TEST-CALL-001",
        event_type="TEST_EVENT",
        trust_score=10,
        action="BLOCK_TRANSACTION",
        claimed_identity="Attacker",
        summary="Testing integrity verification"
    )
    verification = audit_blockchain.verify_hash(event["event_id"])
    assert verification["is_tamper_free"] is True
    assert verification["status"] == "VERIFIED_AUTHENTIC"
