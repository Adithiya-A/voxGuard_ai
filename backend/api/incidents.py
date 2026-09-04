from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import time

from backend.blockchain.audit import audit_blockchain

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

INCIDENTS_DATABASE: Dict[str, Dict[str, Any]] = {
    "INC-10482": {
        "incident_id": "INC-10482",
        "call_id": "VS-2026-00081",
        "severity": "CRITICAL",
        "threat_type": "AI_VOICE_IMPERSONATION",
        "threat_label": "High-Fidelity Neural Voice Clone (CFO Impersonation)",
        "claimed_identity": "Arun Sharma (CFO)",
        "trust_score": 9,
        "ai_probability": 87,
        "speaker_similarity": 94.2,
        "conversation_risk": 91,
        "transaction_risk": 95,
        "recommended_action": "BLOCK_TRANSACTION",
        "current_action": "TRANSACTION_BLOCKED",
        "status": "OPEN",
        "opened_at": "2026-09-04T13:42:31Z",
        "target_account": "Apex Horizon Global Logistics",
        "amount": "₹25,00,000",
        "assigned_analyst": "C. Vance, CISSP"
    },
    "INC-10481": {
        "incident_id": "INC-10481",
        "call_id": "VS-2026-00080",
        "severity": "HIGH",
        "threat_type": "SOCIAL_ENGINEERING",
        "threat_label": "SIM-Swap Credential Harvest Vector",
        "claimed_identity": "Marcus Reed (IT Helpdesk)",
        "trust_score": 27,
        "ai_probability": 22,
        "speaker_similarity": 95.0,
        "conversation_risk": 88,
        "transaction_risk": 15,
        "recommended_action": "REQUIRE_MFA",
        "current_action": "MFA_CHALLENGE_ACTIVE",
        "status": "TRIAGED",
        "opened_at": "2026-09-04T12:16:05Z",
        "target_account": "Internal Active Directory",
        "amount": "N/A",
        "assigned_analyst": "C. Vance, CISSP"
    },
    "INC-10480": {
        "incident_id": "INC-10480",
        "call_id": "VS-2026-00078",
        "severity": "WARNING",
        "threat_type": "UNREGISTERED_TRUNK_INVOICE",
        "threat_label": "Unregistered Vendor Payment Pressure",
        "claimed_identity": "David Ross (Vendor)",
        "trust_score": 42,
        "ai_probability": 38,
        "speaker_similarity": 78.0,
        "conversation_risk": 52,
        "transaction_risk": 65,
        "recommended_action": "INDEPENDENT_CALLBACK",
        "current_action": "CALLBACK_DISPATCHED",
        "status": "IN_PROGRESS",
        "opened_at": "2026-09-04T08:52:10Z",
        "target_account": "Global Freight Ltd",
        "amount": "₹4,50,000",
        "assigned_analyst": "T. Higgins, SOC Tier 2"
    }
}

class ActionRequest(BaseModel):
    action: str  # BLOCK_TRANSACTION, REQUIRE_MFA, INDEPENDENT_CALLBACK, CONTINUE_MONITORING, MARK_CONFIRMED, RESOLVE
    reason: str = "SOC Operator Manual Directive"

@router.get("")
def list_incidents():
    return list(INCIDENTS_DATABASE.values())

@router.get("/{incident_id}")
def get_incident(incident_id: str):
    if incident_id not in INCIDENTS_DATABASE:
        raise HTTPException(status_code=404, detail="Incident not found")
    return INCIDENTS_DATABASE[incident_id]

@router.post("/{incident_id}/action")
def take_action(incident_id: str, req: ActionRequest):
    if incident_id not in INCIDENTS_DATABASE:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    inc = INCIDENTS_DATABASE[incident_id]
    inc["current_action"] = req.action
    
    if req.action == "RESOLVE":
        inc["status"] = "RESOLVED"
    elif req.action == "MARK_CONFIRMED":
        inc["status"] = "CONFIRMED_ATTACK"
    else:
        inc["status"] = "ACTION_ENFORCED"

    # Cryptographic audit anchor
    audit_blockchain.create_event(
        call_id=inc["call_id"],
        event_type=f"INCIDENT_ACTION_{req.action}",
        trust_score=inc["trust_score"],
        action=req.action,
        claimed_identity=inc["claimed_identity"],
        summary=f"Incident {incident_id} updated with action {req.action}: {req.reason}"
    )

    return {
        "success": True,
        "incident": inc,
        "message": f"Action {req.action} successfully applied to {incident_id}"
    }
