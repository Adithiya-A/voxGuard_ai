from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time

from backend.trust.scoring import trust_engine
from backend.models.deepfake_detector import deepfake_detector
from backend.models.speaker_verification import speaker_verification
from backend.models.prosody import prosody_analyzer
from backend.intelligence.conversation import conversation_intelligence
from backend.intelligence.context import context_engine
from backend.blockchain.audit import audit_blockchain

router = APIRouter(prefix="/api/calls", tags=["Calls"])

# In-memory storage for active/historical calls
CALLS_DATABASE: Dict[str, Dict[str, Any]] = {
    "VS-2026-00081": {
        "call_id": "VS-2026-00081",
        "caller": "+1 (415) 890-4412 // UNKNOWN VOIP TRUNK",
        "claimed_identity": "Arun Sharma",
        "claimed_role": "Chief Financial Officer",
        "started_at": "2026-09-04T13:42:10Z",
        "duration": "00:21",
        "duration_seconds": 21,
        "trust_score": 9,
        "risk_level": "CRITICAL",
        "status": "BLOCKED",
        "action": "BLOCK_TRANSACTION",
        "voice": {
            "ai_probability": 87,
            "genuine_probability": 13,
            "spectral_anomaly": 82,
            "harmonic_consistency": 31,
            "voice_naturalness": 24,
            "confidence": 91,
            "vocoder_fingerprint": "Neural Vocoder (ElevenLabs / HiFi-GAN)",
            "detected_artifacts": [
                "Phase-discontinuity in 4.2kHz–7.8kHz bands",
                "Harmonic over-smoothing typical of diffusion vocoder"
            ]
        },
        "speaker": {
            "claimed_identity": "CFO",
            "speaker_name": "Arun Sharma",
            "speaker_role": "Chief Financial Officer",
            "speaker_similarity": 94.2,
            "identity_confidence": "High Match (Target Impersonated)",
            "is_enrolled_match": True
        },
        "prosody": {
            "speech_rate": "Elevated (Rushed Urgency)",
            "pitch_variation": "Flattened Micro-Intonation",
            "pause_pattern": "Anomalous (Robotic Cadence)",
            "behavior_anomaly": 72,
            "coercive_stress_index": 85
        },
        "conversation": {
            "intent": "Coercive Wire Transfer Hijack",
            "authority_impersonation": True,
            "urgency": True,
            "financial_request": True,
            "confidentiality_pressure": True,
            "social_engineering_risk": 91,
            "summary": "Caller mimics executive authority, demands immediate ₹25L transfer to new account, and enforces secrecy."
        },
        "caller_context": {
            "caller_number": "Unknown VoIP Relay",
            "telephony_trunk": "SIP-901 // 8kHz G.711u VoIP Ingress",
            "known_contact": False,
            "registered_device": False,
            "caller_reputation": "Low Confidence / Untrusted Trunk",
            "caller_risk": 85
        },
        "transaction": {
            "requested_amount": 2500000.0,
            "currency": "INR",
            "formatted_amount": "₹25,00,000",
            "new_beneficiary": True,
            "beneficiary_name": "Apex Horizon Global Logistics",
            "beneficiary_account": "HDFC-****-9821",
            "transaction_risk": 95
        },
        "transcript_history": [
            {"timestamp": "00:02", "speaker": "Caller", "text": "Hello? Can you hear me clearly?", "flagged": False},
            {"timestamp": "00:06", "speaker": "Caller", "text": "Hi, this is Arun, the CFO. We have an emergency.", "flagged": True, "category": "Authority Impersonation"},
            {"timestamp": "00:11", "speaker": "Caller", "text": "I need you to transfer ₹25 lakh to the new vendor account immediately.", "flagged": True, "category": "Financial Request"},
            {"timestamp": "00:16", "speaker": "Caller", "text": "Don't discuss this with anyone right now because this acquisition is strictly confidential.", "flagged": True, "category": "Confidentiality Coercion"},
            {"timestamp": "00:20", "speaker": "Caller", "text": "I am boarding a flight now. Release the RTGS immediately or we lose the contract.", "flagged": True, "category": "Extreme Pressure"}
        ],
        "timeline": [
            {"time": "00:00", "score": 82, "label": "Ingress Connected // SIP-901 Trunk Handshake", "type": "info"},
            {"time": "00:05", "score": 80, "label": "Speaker Biometrics: 94.2% match against CFO enrolled voiceprint", "type": "warning"},
            {"time": "00:09", "score": 62, "label": "Acoustic Anomaly: Neural vocoder glottal phase smearing detected (87% AI)", "type": "high"},
            {"time": "00:14", "score": 41, "label": "NLP Coercion Flag: ₹25,00,000 capital transfer directive detected", "type": "critical"},
            {"time": "00:18", "score": 28, "label": "Context Anomaly: Unregistered beneficiary + Unknown Frankfurt VoIP proxy", "type": "critical"},
            {"time": "00:21", "score": 9, "label": "AUTONOMOUS SECURITY DECISION: TRANSACTION BLOCKED & TELEPHONY QUARANTINED", "type": "block"}
        ]
    },
    "VS-2026-00080": {
        "call_id": "VS-2026-00080",
        "caller": "+1 (800) 555-0199 // IT HELPDESK GATEWAY",
        "claimed_identity": "Marcus Reed",
        "claimed_role": "IT Security Helpdesk",
        "started_at": "2026-09-04T12:15:30Z",
        "duration": "01:14",
        "duration_seconds": 74,
        "trust_score": 27,
        "risk_level": "HIGH",
        "status": "MFA_REQUIRED",
        "action": "REQUIRE_MFA",
        "voice": {"ai_probability": 22, "genuine_probability": 78, "spectral_anomaly": 25, "harmonic_consistency": 82, "voice_naturalness": 80, "confidence": 93},
        "speaker": {"claimed_identity": "Helpdesk", "speaker_name": "Marcus Reed", "speaker_similarity": 95.0, "identity_confidence": "High Match"},
        "prosody": {"speech_rate": "Fast", "pitch_variation": "Moderate", "behavior_anomaly": 45, "coercive_stress_index": 78},
        "conversation": {"intent": "Credential Harvesting / SIM-Swap", "authority_impersonation": True, "urgency": True, "financial_request": False, "confidentiality_pressure": False, "social_engineering_risk": 88},
        "caller_context": {"caller_number": "+1 (800) 555-0199", "telephony_trunk": "SIP-002", "known_contact": False, "registered_device": False, "caller_reputation": "Moderate", "caller_risk": 60},
        "transaction": {"requested_amount": 0.0, "currency": "INR", "formatted_amount": "N/A", "new_beneficiary": False, "transaction_risk": 15},
        "transcript_history": [
            {"timestamp": "00:03", "speaker": "Caller", "text": "This is IT Helpdesk. We detected unauthorized portal sign-in.", "flagged": True},
            {"timestamp": "00:09", "speaker": "Caller", "text": "To prevent lockout, verify your one-time SMS verification passcode.", "flagged": True}
        ],
        "timeline": [
            {"time": "00:00", "score": 75, "label": "Call initiated", "type": "info"},
            {"time": "00:09", "score": 27, "label": "Credential harvest attempt flagged - Secondary MFA dispatched", "type": "high"}
        ]
    },
    "VS-2026-00079": {
        "call_id": "VS-2026-00079",
        "caller": "+91 98200 12345 // CORPORATE PBX EXT 401",
        "claimed_identity": "Priya Nair",
        "claimed_role": "VP Operations",
        "started_at": "2026-09-04T10:04:12Z",
        "duration": "03:45",
        "duration_seconds": 225,
        "trust_score": 94,
        "risk_level": "SAFE",
        "status": "ALLOWED",
        "action": "ALLOW",
        "voice": {"ai_probability": 4, "genuine_probability": 96, "spectral_anomaly": 6, "harmonic_consistency": 94, "voice_naturalness": 97, "confidence": 98},
        "speaker": {"claimed_identity": "VP_OPS", "speaker_name": "Priya Nair", "speaker_similarity": 96.5, "identity_confidence": "High"},
        "prosody": {"speech_rate": "Normal", "pitch_variation": "Natural", "behavior_anomaly": 8, "coercive_stress_index": 12},
        "conversation": {"intent": "Routine Operations Sync", "authority_impersonation": False, "urgency": False, "financial_request": False, "confidentiality_pressure": False, "social_engineering_risk": 8},
        "caller_context": {"caller_number": "+91 98200 12345", "telephony_trunk": "CORP-PBX-01", "known_contact": True, "registered_device": True, "caller_reputation": "High Confidence", "caller_risk": 5},
        "transaction": {"requested_amount": 0.0, "currency": "INR", "formatted_amount": "N/A", "new_beneficiary": False, "transaction_risk": 5},
        "transcript_history": [
            {"timestamp": "00:02", "speaker": "Priya", "text": "Hi team, confirming the operations schedule for next week.", "flagged": False}
        ],
        "timeline": [
            {"time": "00:00", "score": 95, "label": "Corporate PBX Attestation Verified", "type": "info"},
            {"time": "00:15", "score": 94, "label": "Continuous biometric stream validated clean", "type": "safe"}
        ]
    },
    "VS-2026-00078": {
        "call_id": "VS-2026-00078",
        "caller": "+44 20 7946 0912 // OUTBOUND RELAY",
        "claimed_identity": "David Ross",
        "claimed_role": "Vendor Procurement Lead",
        "started_at": "2026-09-04T08:51:00Z",
        "duration": "01:50",
        "duration_seconds": 110,
        "trust_score": 42,
        "risk_level": "WARNING",
        "status": "CALLBACK_REQUIRED",
        "action": "INDEPENDENT_CALLBACK",
        "voice": {"ai_probability": 38, "genuine_probability": 62, "spectral_anomaly": 41, "harmonic_consistency": 64, "voice_naturalness": 58, "confidence": 88},
        "speaker": {"claimed_identity": "VENDOR", "speaker_name": "David Ross", "speaker_similarity": 78.0, "identity_confidence": "Moderate"},
        "prosody": {"speech_rate": "Moderate", "pitch_variation": "Slightly Flattened", "behavior_anomaly": 42, "coercive_stress_index": 54},
        "conversation": {"intent": "Invoice Payment Query", "authority_impersonation": False, "urgency": True, "financial_request": True, "confidentiality_pressure": False, "social_engineering_risk": 52},
        "caller_context": {"caller_number": "+44 20 7946 0912", "telephony_trunk": "SIP-UK-04", "known_contact": False, "registered_device": False, "caller_reputation": "Moderate", "caller_risk": 48},
        "transaction": {"requested_amount": 450000.0, "currency": "INR", "formatted_amount": "₹4,50,000", "new_beneficiary": True, "transaction_risk": 65},
        "transcript_history": [
            {"timestamp": "00:05", "speaker": "David", "text": "Following up on invoice 8491, please expedite processing.", "flagged": True}
        ],
        "timeline": [
            {"time": "00:00", "score": 68, "label": "Call Connected", "type": "info"},
            {"time": "00:20", "score": 42, "label": "Independent callback initiated to registered vendor switchboard", "type": "warning"}
        ]
    }
}

class AnalyzeRequest(BaseModel):
    call_id: str
    transcript_chunk: Optional[str] = None
    chunk_index: int = 0
    scenario: Optional[str] = "clone"
    claimed_identity: Optional[str] = "CFO"

@router.get("")
def list_calls():
    return list(CALLS_DATABASE.values())

@router.get("/{call_id}")
def get_call(call_id: str):
    if call_id not in CALLS_DATABASE:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return CALLS_DATABASE[call_id]

@router.post("/analyze")
def analyze_call_chunk(req: AnalyzeRequest):
    """
    Continuous analysis endpoint returning updated trust scores and multi-signal metrics.
    """
    call_id = req.call_id
    call = CALLS_DATABASE.get(call_id)
    if not call:
        # Create dynamically
        call = {
            "call_id": call_id,
            "caller": "+1 (415) 890-4412 // UNKNOWN VOIP TRUNK",
            "claimed_identity": "Arun Sharma",
            "claimed_role": "Chief Financial Officer",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration": "00:00",
            "duration_seconds": 0,
            "trust_score": 82,
            "risk_level": "WARNING",
            "status": "MONITORING",
            "action": "MONITOR",
            "transcript_history": [],
            "timeline": []
        }
        CALLS_DATABASE[call_id] = call

    return call
