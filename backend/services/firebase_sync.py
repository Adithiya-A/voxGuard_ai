import logging
import time
from typing import Any, Dict, Optional

from backend.config import settings

logger = logging.getLogger("voxguard.firebase")

_firebase_app = None
_firebase_error: Optional[str] = None
_initialized = False


def firebase_status() -> Dict[str, Any]:
    return {
        "configured": bool(settings.FIREBASE_PROJECT_ID and settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY),
        "initialized": _firebase_app is not None,
        "error": _firebase_error,
        "status": "OK" if _firebase_app is not None else (
            "NOT_CONFIGURED" if not (settings.FIREBASE_PROJECT_ID and settings.FIREBASE_PRIVATE_KEY) else "FIREBASE_UNAVAILABLE"
        ),
    }


def init_firebase() -> bool:
    global _firebase_app, _firebase_error, _initialized
    if _initialized:
        return _firebase_app is not None
    _initialized = True
    if not (settings.FIREBASE_PROJECT_ID and settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY):
        _firebase_error = "Firebase Admin credentials are not configured"
        logger.info("[FIREBASE] Not configured — local SQLite remains primary persistence.")
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials

        private_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": settings.FIREBASE_PROJECT_ID,
            "private_key": private_key,
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        _firebase_app = firebase_admin.initialize_app(cred)
        _firebase_error = None
        logger.info("[FIREBASE] Admin SDK initialized for cloud sync (not used for live audio).")
        return True
    except Exception as e:
        _firebase_app = None
        _firebase_error = str(e)
        logger.warning(f"[FIREBASE] Unavailable: {e}")
        return False


def sync_document(collection: str, doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort Firestore write. Never used as audio transport."""
    try:
        if not init_firebase():
            return {"ok": False, "status": "FIREBASE_UNAVAILABLE", "error": _firebase_error}
        from firebase_admin import firestore
        db = firestore.client()
        payload = dict(data)
        payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        db.collection(collection).document(str(doc_id)).set(payload, merge=True)
        return {"ok": True, "status": "OK"}
    except Exception as e:
        logger.warning(f"[FIREBASE] Sync failed for {collection}/{doc_id}: {e}")
        return {"ok": False, "status": "FIREBASE_UNAVAILABLE", "error": str(e)}


def sync_call(call_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return sync_document("calls", call_id, data)


def sync_incident(incident_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return sync_document("incidents", incident_id, data)


def sync_speaker(speaker_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return sync_document("speakers", speaker_id, data)
