import asyncio
import json
import time
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api import calls, incidents, analytics, audit, demo, settings as settings_api
from backend.blockchain.audit import audit_blockchain

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks"
)

# Enable CORS for Vite frontend (localhost:5173, localhost:3000, 127.0.0.1:*)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST Routers
app.include_router(calls.router)
app.include_router(incidents.router)
app.include_router(analytics.router)
app.include_router(audit.router)
app.include_router(demo.router)
app.include_router(settings_api.router)

@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "tagline": settings.TAGLINE,
        "active_models": {
            "deepfake_detector": "ONLINE (v2.4 Spectral Ensemble)",
            "speaker_verification": "ONLINE (ECAPA-TDNN)",
            "prosody_analyzer": "ONLINE (Biometrics-v1.8)",
            "conversation_intelligence": "ONLINE (Gemini/Heuristic)",
            "trust_engine": "ONLINE (Deterministic 6-Signal)",
            "blockchain_audit": "ONLINE (SHA-256 Ledger Anchor)"
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

# ==================== WEBSOCKET CONNECTION MANAGER ====================
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = set()
        self.active_connections[room].add(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        if room in self.active_connections:
            self.active_connections[room].discard(websocket)
            if not self.active_connections[room]:
                del self.active_connections[room]

    async def broadcast(self, room: str, message: dict):
        if room in self.active_connections:
            for connection in list(self.active_connections[room]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(room, connection)

manager = ConnectionManager()

@app.websocket("/ws/call/{call_id}")
async def websocket_call_endpoint(websocket: WebSocket, call_id: str):
    await manager.connect(call_id, websocket)
    try:
        # Send initial confirmation
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "call_id": call_id,
            "status": "STREAM_ACTIVE",
            "timestamp": time.strftime("%H:%M:%S", time.gmtime())
        })
        while True:
            data = await websocket.receive_text()
            # Handle client commands or audio metadata
            payload = json.loads(data) if data.startswith("{") else {"action": data}
            
            if payload.get("action") == "TRIGGER_SCENARIO":
                scenario_key = payload.get("scenario", "clone")
                steps = demo.SCENARIOS_DATA.get(scenario_key, demo.SCENARIOS_DATA["clone"])["steps"]
                
                # Stream steps progressively to simulate continuous call analysis
                for step in steps:
                    await manager.broadcast(call_id, {
                        "type": "TRUST_UPDATE",
                        "call_id": call_id,
                        "data": step
                    })
                    # Pause between steps (1.5s simulated playback cadence)
                    await asyncio.sleep(1.5)

            elif payload.get("action") == "BLOCK_TRANSACTION":
                # Create incident & blockchain anchor
                audit_blockchain.create_event(
                    call_id=call_id,
                    event_type="MANUAL_BLOCK_ENFORCED",
                    trust_score=9,
                    action="BLOCK_TRANSACTION",
                    claimed_identity="CFO Impersonator",
                    summary=f"Operator manually enforced block on call {call_id}."
                )
                await manager.broadcast(call_id, {
                    "type": "SECURITY_ACTION_TRIGGERED",
                    "action": "BLOCK_TRANSACTION",
                    "call_id": call_id,
                    "reason": "AI voice impersonation attack mitigated."
                })
    except WebSocketDisconnect:
        manager.disconnect(call_id, websocket)
    except Exception:
        manager.disconnect(call_id, websocket)

@app.websocket("/ws/demo/{session_id}")
async def websocket_demo_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        await websocket.send_json({
            "type": "DEMO_READY",
            "session_id": session_id,
            "latency": "14ms"
        })
        while True:
            msg = await websocket.receive_text()
            # Echo or broadcast demo telemetry
            await websocket.send_json({"echo": msg})
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
