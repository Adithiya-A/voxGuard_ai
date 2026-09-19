from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
import numpy as np

class SpeakerRecord(BaseModel):
    speaker_id: str
    display_name: str
    role: str = "Enrolled Executive"
    enrolled_fips: Optional[str] = None
    embedding: Optional[List[float]] = None
    embedding_dimension: int = 192
    threshold: float = 0.80
    model: str = "speechbrain/spkrec-ecapa-voxceleb"
    created_at: str
    updated_at: str
    is_synthetic: bool = False
    status: str = "ENROLLED"

    def get_embedding_numpy(self) -> Optional[np.ndarray]:
        if self.embedding is None:
            return None
        return np.array(self.embedding, dtype=np.float32)

    @classmethod
    def from_row(cls, row: Any) -> "SpeakerRecord":
        emb_val = None
        if row["embedding"]:
            try:
                emb_val = json.loads(row["embedding"])
            except Exception:
                emb_val = None

        return cls(
            speaker_id=row["speaker_id"],
            display_name=row["display_name"],
            role=row["role"],
            enrolled_fips=row["enrolled_fips"],
            embedding=emb_val,
            embedding_dimension=row["embedding_dimension"],
            threshold=row["threshold"],
            model=row["model"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_synthetic=bool(row["is_synthetic"]),
            status=row["status"]
        )


class CallRecord(BaseModel):
    call_id: str
    source: str = "LIVE_MICROPHONE"
    mode: str = "REAL"
    status: str = "ACTIVE"
    claimed_speaker_id: Optional[str] = None
    claimed_speaker_name: Optional[str] = None
    caller: str = "Browser Microphone Stream"
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: float = 0.0
    duration_formatted: str = "00:00"
    sample_rate: int = 16000
    channel_count: int = 1
    trust_score: int = 85
    trust_level: str = "SAFE"
    security_decision: str = "ALLOW"
    action: str = "ALLOW"
    anti_spoof_prediction: str = "INCONCLUSIVE"
    spoof_probability: Optional[float] = None
    genuine_probability: Optional[float] = None
    raw_anti_spoof_score: Optional[float] = None
    speaker_status: str = "INCONCLUSIVE"
    speaker_similarity: float = 0.0
    speaker_threshold: float = 0.80
    speaker_windows: int = 0
    total_windows: int = 0
    speech_windows: int = 0
    possible_voice_clone: bool = False
    telemetry_summary: Optional[Dict[str, Any]] = None
    timeline: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_row(cls, row: Any) -> "CallRecord":
        telemetry = None
        if row["telemetry_summary"]:
            try:
                telemetry = json.loads(row["telemetry_summary"])
            except Exception:
                telemetry = None

        tl = None
        if row["timeline_json"]:
            try:
                tl = json.loads(row["timeline_json"])
            except Exception:
                tl = None

        return cls(
            call_id=row["call_id"],
            source=row["source"],
            mode=row["mode"],
            status=row["status"],
            claimed_speaker_id=row["claimed_speaker_id"],
            claimed_speaker_name=row["claimed_speaker_name"],
            caller=row["caller"] or "Browser Microphone Stream",
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_seconds=float(row["duration_seconds"] or 0.0),
            duration_formatted=row["duration_formatted"] or "00:00",
            sample_rate=int(row["sample_rate"] or 16000),
            channel_count=int(row["channel_count"] or 1),
            trust_score=int(row["trust_score"] if row["trust_score"] is not None else 85),
            trust_level=row["trust_level"] or "SAFE",
            security_decision=row["security_decision"] or "ALLOW",
            action=row["action"] or "ALLOW",
            anti_spoof_prediction=row["anti_spoof_prediction"] or "INCONCLUSIVE",
            spoof_probability=float(row["spoof_probability"]) if row["spoof_probability"] is not None else None,
            genuine_probability=float(row["genuine_probability"]) if row["genuine_probability"] is not None else None,
            raw_anti_spoof_score=float(row["raw_anti_spoof_score"]) if row["raw_anti_spoof_score"] is not None else None,
            speaker_status=row["speaker_status"] or "INCONCLUSIVE",
            speaker_similarity=float(row["speaker_similarity"] or 0.0),
            speaker_threshold=float(row["speaker_threshold"] or 0.80),
            speaker_windows=int(row["speaker_windows"] or 0),
            total_windows=int(row["total_windows"] or 0),
            speech_windows=int(row["speech_windows"] or 0),
            possible_voice_clone=bool(row["possible_voice_clone"]),
            telemetry_summary=telemetry,
            timeline=tl
        )

    def to_api_dict(self) -> Dict[str, Any]:
        """Maps to frontend-expected call format (compatible with CallHistory and Investigation)."""
        ai_pct = int(round(self.spoof_probability * 100)) if self.spoof_probability is not None else 0
        gen_pct = int(round(self.genuine_probability * 100)) if self.genuine_probability is not None else 100

        res = {
            "call_id": self.call_id,
            "source": self.source,
            "mode": self.mode,
            "caller": self.caller,
            "claimed_identity": self.claimed_speaker_name or self.claimed_speaker_id or "Enrolled Executive",
            "claimed_role": "Executive",
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": self.duration_formatted,
            "duration_seconds": int(round(self.duration_seconds)),
            "trust_score": self.trust_score,
            "risk_level": self.trust_level,
            "status": self.status,
            "action": self.action,
            "voice": {
                "ai_probability": ai_pct,
                "genuine_probability": gen_pct,
                "anti_spoof_prediction": self.anti_spoof_prediction,
                "spoof_probability": self.spoof_probability,
                "genuine_probability": self.genuine_probability,
                "confidence": max(ai_pct, gen_pct),
                "spectral_anomaly": (self.telemetry_summary or {}).get("spectral_anomaly", 0),
                "harmonic_consistency": (self.telemetry_summary or {}).get("harmonic_consistency", 90),
                "voice_naturalness": (self.telemetry_summary or {}).get("voice_naturalness", 90),
            },
            "speaker": {
                "claimed_identity": self.claimed_speaker_id,
                "speaker_name": self.claimed_speaker_name or self.claimed_speaker_id,
                "speaker_similarity": self.speaker_similarity,
                "identity_confidence": self.speaker_status,
                "is_enrolled_match": (self.speaker_status == "MATCH"),
                "status": self.speaker_status,
                "threshold": self.speaker_threshold,
                "windows": self.speaker_windows
            },
            "prosody": (self.telemetry_summary or {}).get("prosody", {
                "speech_rate": "Normal",
                "pitch_variation": "Natural",
                "behavior_anomaly": 15,
                "coercive_stress_index": 20
            }),
            "conversation": (self.telemetry_summary or {}).get("conversation", {
                "intent": "Live Microphone Attestation",
                "authority_impersonation": False,
                "urgency": False,
                "financial_request": False,
                "confidentiality_pressure": False,
                "social_engineering_risk": 10,
                "summary": "Live microphone speech session analyzed by VoxGuard neural defense engine."
            }),
            "caller_context": {
                "caller_number": "Live Microphone",
                "telephony_trunk": "Browser WebAudio / WebSocket Ingress",
                "known_contact": True,
                "registered_device": True,
                "caller_reputation": "High Confidence",
                "caller_risk": 5
            },
            "transaction": {
                "requested_amount": 0.0,
                "currency": "INR",
                "formatted_amount": "N/A",
                "new_beneficiary": False,
                "transaction_risk": 0
            },
            "transcript_history": (self.telemetry_summary or {}).get("transcript_history", []),
            "timeline": self.timeline or []
        }
        return res
