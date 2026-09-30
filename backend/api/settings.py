from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, List
from backend.trust.scoring import trust_engine
from backend.trust.rules import policy_matrix

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class WeightsUpdate(BaseModel):
    voice_synthetic: float
    speaker_anomaly: float
    prosody_anomaly: float
    conversation_risk: float
    caller_risk: float
    transaction_risk: float

@router.get("")
def get_settings():
    return {
        "weights": trust_engine.weights,
        "policies": policy_matrix.rules,
        "telephony_integrations": [
            {"provider": "Twilio Elastic SIP Trunk", "status": "CONNECTED", "latency": "14ms", "encryption": "TLS 1.3 / SRTP"},
            {"provider": "Asterisk PBX Internal Core", "status": "CONNECTED", "latency": "8ms", "encryption": "SRTP"},
            {"provider": "WebRTC Low-Latency Mesh", "status": "ACTIVE", "latency": "24ms", "encryption": "DTLS-SRTP"}
        ],
        "system_status": {
            "deepfake_engine": "ACTIVE (Spectrogram + FFT Anomaly)",
            "speaker_verification": "ACTIVE (ECAPA-TDNN)",
            "conversation_nlp": "ACTIVE (Gemini + Local Fallback)",
            "blockchain_audit": "ACTIVE (SHA-256 Polygon Testnet Anchor)"
        }
    }

@router.post("/weights")
def update_weights(req: WeightsUpdate):
    trust_engine.update_weights(req.model_dump())
    return {"success": True, "updated_weights": trust_engine.weights}
