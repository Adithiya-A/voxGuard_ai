from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from backend.blockchain.audit import audit_blockchain

router = APIRouter(prefix="/api/audit-logs", tags=["Audit"])

@router.get("")
def get_audit_logs():
    return audit_blockchain.get_logs()

@router.get("/verify/{event_id}")
def verify_event_hash(event_id: str):
    res = audit_blockchain.verify_hash(event_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail="Event hash not found in ledger")
    return res
