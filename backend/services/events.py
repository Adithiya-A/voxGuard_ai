import time
from typing import Any, Dict, Optional


def ws_event(event_type: str, session_id: str, data: Optional[Dict[str, Any]] = None, **compat) -> Dict[str, Any]:
    payload = {
        "type": event_type,
        "session_id": session_id,
        "call_id": session_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data or {},
    }
    payload.update(compat)
    return payload
