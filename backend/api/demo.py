from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter(prefix="/api/demo", tags=["Demo"])

SCENARIOS_DATA: Dict[str, Dict[str, Any]] = {
    "clone": {
        "scenario_id": "clone",
        "title": "Scenario 2: AI Voice Clone Impersonation",
        "target": "Arun Sharma (CFO)",
        "vector": "ElevenLabs Multilingual v2 + High-Value Capital Extortion",
        "steps": [
            {
                "step_index": 0,
                "timestamp": "00:00",
                "trust_score": 82,
                "risk_level": "WARNING",
                "action": "ALLOW",
                "transcript": "Hello? Can you hear me clearly?",
                "voice": {"ai_probability": 15, "spectral_anomaly": 18, "harmonic_consistency": 85, "voice_naturalness": 88, "confidence": 91},
                "speaker": {"speaker_similarity": 82.0, "identity_confidence": "Initial Ingress"},
                "prosody": {"speech_rate": "Normal", "pitch_variation": "Natural", "behavior_anomaly": 20, "coercive_stress_index": 25},
                "conversation": {"intent": "Line Check", "urgency": False, "financial_request": False, "authority_impersonation": False, "social_engineering_risk": 15},
                "caller": {"caller_number": "Unknown VoIP Relay", "known_contact": False, "caller_risk": 65},
                "transaction": {"requested_amount": 0, "formatted_amount": "N/A", "new_beneficiary": False, "transaction_risk": 10},
                "event_label": "Call Connected // SIP Ingress Established"
            },
            {
                "step_index": 1,
                "timestamp": "00:05",
                "trust_score": 80,
                "risk_level": "WARNING",
                "action": "ALLOW",
                "transcript": "Hi, this is Arun, the CFO. We have an emergency.",
                "voice": {"ai_probability": 34, "spectral_anomaly": 38, "harmonic_consistency": 70, "voice_naturalness": 72, "confidence": 92},
                "speaker": {"speaker_similarity": 94.2, "identity_confidence": "High Match (Target Impersonated)"},
                "prosody": {"speech_rate": "Elevated", "pitch_variation": "Slightly Strained", "behavior_anomaly": 48, "coercive_stress_index": 62},
                "conversation": {"intent": "Executive Impersonation", "urgency": True, "financial_request": False, "authority_impersonation": True, "social_engineering_risk": 55},
                "caller": {"caller_number": "Unknown VoIP Relay", "known_contact": False, "caller_risk": 75},
                "transaction": {"requested_amount": 0, "formatted_amount": "N/A", "new_beneficiary": False, "transaction_risk": 10},
                "event_label": "Speaker Voiceprint Matched to CFO (94.2% Similarity)"
            },
            {
                "step_index": 2,
                "timestamp": "00:09",
                "trust_score": 62,
                "risk_level": "WARNING",
                "action": "WARN",
                "transcript": "I need you to transfer ₹25 lakh to the new vendor account immediately.",
                "voice": {"ai_probability": 87, "spectral_anomaly": 82, "harmonic_consistency": 31, "voice_naturalness": 24, "confidence": 94},
                "speaker": {"speaker_similarity": 94.2, "identity_confidence": "High Match (Target Impersonated)"},
                "prosody": {"speech_rate": "Elevated (Rushed Urgency)", "pitch_variation": "Flattened Micro-Intonation", "behavior_anomaly": 72, "coercive_stress_index": 85},
                "conversation": {"intent": "Coercive Wire Transfer Hijack", "urgency": True, "financial_request": True, "authority_impersonation": True, "social_engineering_risk": 82},
                "caller": {"caller_number": "Unknown VoIP Relay", "known_contact": False, "caller_risk": 80},
                "transaction": {"requested_amount": 2500000, "formatted_amount": "₹25,00,000", "new_beneficiary": True, "transaction_risk": 85},
                "event_label": "Synthetic Acoustic Artifact Detected // AI Probability 87%"
            },
            {
                "step_index": 3,
                "timestamp": "00:14",
                "trust_score": 41,
                "risk_level": "HIGH",
                "action": "REQUIRE_MFA",
                "transcript": "Don't discuss this with anyone right now because this acquisition is strictly confidential.",
                "voice": {"ai_probability": 88, "spectral_anomaly": 84, "harmonic_consistency": 29, "voice_naturalness": 22, "confidence": 94},
                "speaker": {"speaker_similarity": 94.2, "identity_confidence": "High Match (Target Impersonated)"},
                "prosody": {"speech_rate": "Elevated (Rushed Urgency)", "pitch_variation": "Flattened Micro-Intonation", "behavior_anomaly": 78, "coercive_stress_index": 89},
                "conversation": {"intent": "Coercive Wire Transfer Hijack", "urgency": True, "financial_request": True, "authority_impersonation": True, "social_engineering_risk": 91},
                "caller": {"caller_number": "Unknown VoIP Relay", "known_contact": False, "caller_risk": 85},
                "transaction": {"requested_amount": 2500000, "formatted_amount": "₹25,00,000", "new_beneficiary": True, "transaction_risk": 95},
                "event_label": "BEC Coercion Detected // Confidentiality Pressure Enforced"
            },
            {
                "step_index": 4,
                "timestamp": "00:18",
                "trust_score": 28,
                "risk_level": "CRITICAL",
                "action": "REQUIRE_MFA",
                "transcript": "I am boarding a flight now. Release the RTGS immediately or we lose the contract.",
                "voice": {"ai_probability": 89, "spectral_anomaly": 86, "harmonic_consistency": 26, "voice_naturalness": 18, "confidence": 95},
                "speaker": {"speaker_similarity": 94.2, "identity_confidence": "High Match (Target Impersonated)"},
                "prosody": {"speech_rate": "High Coercion", "pitch_variation": "Flattened", "behavior_anomaly": 82, "coercive_stress_index": 94},
                "conversation": {"intent": "Coercive Wire Transfer Hijack", "urgency": True, "financial_request": True, "authority_impersonation": True, "social_engineering_risk": 96},
                "caller": {"caller_number": "Unknown VoIP Relay", "known_contact": False, "caller_risk": 90},
                "transaction": {"requested_amount": 2500000, "formatted_amount": "₹25,00,000", "new_beneficiary": True, "transaction_risk": 98},
                "event_label": "High-Risk Unverified Beneficiary Account Flagged"
            },
            {
                "step_index": 5,
                "timestamp": "00:21",
                "trust_score": 9,
                "risk_level": "CRITICAL",
                "action": "BLOCK_TRANSACTION",
                "transcript": "[INTERCEPT ACTIVATED] Audio trunk quarantined by VoxGuard autonomous engine.",
                "voice": {"ai_probability": 92, "spectral_anomaly": 88, "harmonic_consistency": 24, "voice_naturalness": 14, "confidence": 96},
                "speaker": {"speaker_similarity": 94.2, "identity_confidence": "High Match (Target Impersonated)"},
                "prosody": {"speech_rate": "Terminated", "pitch_variation": "Flattened", "behavior_anomaly": 85, "coercive_stress_index": 95},
                "conversation": {"intent": "Coercive Wire Transfer Hijack", "urgency": True, "financial_request": True, "authority_impersonation": True, "social_engineering_risk": 98},
                "caller": {"caller_number": "Unknown VoIP Relay", "known_contact": False, "caller_risk": 95},
                "transaction": {"requested_amount": 2500000, "formatted_amount": "₹25,00,000", "new_beneficiary": True, "transaction_risk": 99},
                "event_label": "CRITICAL THREAT MITIGATED: TRANSACTION BLOCKED & TELEPHONY DISCONNECTED"
            }
        ]
    },
    "genuine": {
        "scenario_id": "genuine",
        "title": "Scenario 1: Genuine CFO Call",
        "target": "Arun Sharma (CFO)",
        "vector": "Enrolled Voiceprint Match + Clean Harmonics + Routine Query",
        "steps": [
            {
                "step_index": 0,
                "timestamp": "00:02",
                "trust_score": 94,
                "risk_level": "SAFE",
                "action": "ALLOW",
                "transcript": "Good afternoon, finance team. Checking in on the Q3 audit report.",
                "voice": {"ai_probability": 4, "spectral_anomaly": 6, "harmonic_consistency": 95, "voice_naturalness": 96, "confidence": 98},
                "speaker": {"speaker_similarity": 96.2, "identity_confidence": "Authentic Enrolled Match"},
                "prosody": {"speech_rate": "Normal Cadence", "pitch_variation": "Natural Harmonic Dynamic", "behavior_anomaly": 8, "coercive_stress_index": 12},
                "conversation": {"intent": "Routine Audit Sync", "urgency": False, "financial_request": False, "authority_impersonation": False, "social_engineering_risk": 6},
                "caller": {"caller_number": "+91 98200 12345 (Corporate PBX)", "known_contact": True, "caller_risk": 5},
                "transaction": {"requested_amount": 0, "formatted_amount": "N/A", "new_beneficiary": False, "transaction_risk": 5},
                "event_label": "Caller Biometric Verified // Trust Score 94 (ALLOW)"
            }
        ]
    },
    "social_eng": {
        "scenario_id": "social_eng",
        "title": "Scenario 3: Sophisticated Social Engineering",
        "target": "Internal Employee",
        "vector": "Human Voice Spoof / IT Helpdesk Credential Harvest",
        "steps": [
            {
                "step_index": 0,
                "timestamp": "00:03",
                "trust_score": 68,
                "risk_level": "WARNING",
                "action": "WARN",
                "transcript": "Hey there, this is IT Security Helpdesk. We detected suspicious sign-ins on your portal.",
                "voice": {"ai_probability": 18, "spectral_anomaly": 20, "harmonic_consistency": 82, "voice_naturalness": 84, "confidence": 91},
                "speaker": {"speaker_similarity": 94.8, "identity_confidence": "Corporate Directory Match"},
                "prosody": {"speech_rate": "Fast", "pitch_variation": "Moderate", "behavior_anomaly": 38, "coercive_stress_index": 65},
                "conversation": {"intent": "Helpdesk Triage", "urgency": True, "financial_request": False, "authority_impersonation": True, "social_engineering_risk": 64},
                "caller": {"caller_number": "+1 (800) 555-0199", "known_contact": False, "caller_risk": 55},
                "transaction": {"requested_amount": 0, "formatted_amount": "N/A", "new_beneficiary": False, "transaction_risk": 15},
                "event_label": "Helpdesk Impersonation Detected"
            },
            {
                "step_index": 1,
                "timestamp": "00:12",
                "trust_score": 34,
                "risk_level": "HIGH",
                "action": "REQUIRE_MFA",
                "transcript": "To prevent account lockout, I need you to confirm your one-time SMS verification passcode.",
                "voice": {"ai_probability": 22, "spectral_anomaly": 24, "harmonic_consistency": 80, "voice_naturalness": 82, "confidence": 92},
                "speaker": {"speaker_similarity": 95.0, "identity_confidence": "Corporate Directory Match"},
                "prosody": {"speech_rate": "Urgent", "pitch_variation": "Flattened", "behavior_anomaly": 54, "coercive_stress_index": 82},
                "conversation": {"intent": "Credential Harvesting", "urgency": True, "financial_request": False, "authority_impersonation": True, "social_engineering_risk": 88},
                "caller": {"caller_number": "+1 (800) 555-0199", "known_contact": False, "caller_risk": 68},
                "transaction": {"requested_amount": 0, "formatted_amount": "N/A", "new_beneficiary": False, "transaction_risk": 20},
                "event_label": "Out-of-Band OTP Solicit Flagged // REQUIRE SECONDARY VERIFICATION"
            }
        ]
    }
}

@router.get("/scenarios")
def list_scenarios():
    return [
        {
            "id": k,
            "title": v["title"],
            "target": v["target"],
            "vector": v["vector"],
            "step_count": len(v["steps"])
        }
        for k, v in SCENARIOS_DATA.items()
    ]

@router.get("/scenario/{scenario_id}")
def get_scenario(scenario_id: str):
    if scenario_id not in SCENARIOS_DATA:
        return SCENARIOS_DATA["clone"]
    return SCENARIOS_DATA[scenario_id]
