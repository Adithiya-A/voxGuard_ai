import asyncio
import json
import logging
import os
import time
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("voxguard.main")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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

from backend.audio.stream_processor import stream_processor
from backend.models.deepfake_detector import deepfake_detector
from backend.models.speaker_verifier import speaker_verifier
from backend.models.transcription import transcription_service
from backend.audio.preprocessing import load_audio_bytes, preprocess_for_speaker_model
from backend.database.db import init_db
from backend.services.events import ws_event
from backend.services.firebase_sync import init_firebase, firebase_status
from backend.services import live_semantics
from pydantic import BaseModel
from typing import Optional
import numpy as np

@app.on_event("startup")
def startup_event():
    """Ensure database schema is initialized and hydrate enrolled speakers on startup."""
    init_db()
    speaker_verifier.reload_from_database()
    init_firebase()

@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "tagline": settings.TAGLINE,
        "active_models": {
            "audio_stream_processor": "ONLINE (16kHz Resampling / 3s Rolling Window)",
            "vad": "ONLINE (DSP VAD - RMS/ZCR/SNR)",
            "prosody_analyzer": "ONLINE (DSP Autocorrelation F0/Cadence)",
            "deepfake_detector": f"ONLINE (AASIST - ASVspoof2019-LA, Device: {deepfake_detector.device})",
            "speaker_verification": f"ONLINE (ECAPA-TDNN - VoxCeleb, Device: {speaker_verifier.device})",
            "transcription": transcription_service.get_state(),
            "conversation_intelligence": "ONLINE (Gemini/Heuristic)",
            "trust_engine": "ONLINE (Dynamic Attestation)",
            "firebase": firebase_status(),
            "blockchain_audit": "ONLINE (SHA-256 Ledger Anchor)"
        },
        "anti_spoof": {
            "available": True,
            "model": deepfake_detector.model_name,
            "model_version": deepfake_detector.model_version,
            "loaded": deepfake_detector.is_loaded(),
            "device": deepfake_detector.device
        },
        "speaker_verification": speaker_verifier.get_state(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

import re
from fastapi import HTTPException

class EnrollRequest(BaseModel):
    speaker_id: str
    display_name: str
    role: Optional[str] = "Enrolled Executive"
    audio_base64: Optional[str] = None
    frequency_hz: Optional[float] = None

@app.get("/api/speakers")
def get_enrolled_speakers():
    """Returns list of currently enrolled executive voiceprints."""
    return speaker_verifier.list_enrolled_speakers()

@app.post("/api/speakers/enroll")
def enroll_speaker_profile(req: EnrollRequest):
    """
    Enrolls a new executive voiceprint embedding.
    Validates speaker ID format, prevents duplicates, extracts real 192-d ECAPA embedding.
    Does NOT retain raw audio.
    """
    clean_id = (req.speaker_id or "").strip()
    if not clean_id:
        raise HTTPException(status_code=400, detail="Speaker ID is required.")
    if not re.match(r"^[a-z0-9_-]{1,64}$", clean_id):
        raise HTTPException(
            status_code=400,
            detail="Speaker ID must contain only lowercase letters, numbers, underscores, and hyphens (max 64 chars)."
        )
    if clean_id in speaker_verifier.enrolled_speakers:
        raise HTTPException(status_code=400, detail=f"Speaker ID '{clean_id}' already exists.")

    clean_name = (req.display_name or "").strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Display name is required.")

    if req.audio_base64:
        import base64
        try:
            audio_bytes = base64.b64decode(req.audio_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 encoding for audio.")
        
        if not audio_bytes or len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

        try:
            audio, sr = load_audio_bytes(audio_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to process audio format: {e}")

        if audio is None or len(audio) == 0:
            raise HTTPException(status_code=400, detail="Audio file could not be decoded.")

        # Minimum audio length for ECAPA temporal convolutions (at least 4000 samples / 0.25s at 16kHz)
        if len(audio) < 4000:
            raise HTTPException(status_code=400, detail="Voice sample is too short. Please provide at least 10 seconds of speech.")

        # Digital silence check
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 1e-4:
            raise HTTPException(status_code=400, detail="Voice sample contains insufficient speech (digital silence detected).")

    elif req.frequency_hz:
        sr = 16000
        t = np.linspace(0, 3.0, sr * 3, endpoint=False, dtype=np.float32)
        audio = (0.6 * np.sin(2 * np.pi * req.frequency_hz * t) + 
                 0.3 * np.sin(4 * np.pi * req.frequency_hz * t)).astype(np.float32)
    else:
        raise HTTPException(status_code=400, detail="Audio data is required for voice enrollment.")
        
    result = speaker_verifier.enroll_speaker(
        speaker_id=clean_id,
        display_name=clean_name,
        audio=audio,
        sample_rate=sr,
        role=req.role or "Enrolled Executive"
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Enrollment failed"))
    try:
        from backend.services.firebase_sync import sync_speaker
        sync_speaker(clean_id, {k: v for k, v in result.items() if k != "embedding"})
    except Exception:
        pass
    return result

@app.delete("/api/speakers/{speaker_id}")
def delete_speaker_profile(speaker_id: str):
    """
    Deletes an enrolled speaker voiceprint and purges their stored reference embedding.
    """
    clean_id = (speaker_id or "").strip().lower()
    result = speaker_verifier.delete_speaker(clean_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", f"Speaker '{clean_id}' not found"))
    return result

class ValidateAudioRequest(BaseModel):
    audio_base64: str
    sample_rate: Optional[int] = 16000
    claimed_speaker_id: Optional[str] = "cfo_arun"

@app.post("/api/debug/validate-audio")
def validate_audio_diagnostics(req: ValidateAudioRequest):
    """
    Diagnostic offline validation endpoint (Phase H).
    Allows evaluating the exact same audio payload through:
    canonical preprocessing, diagnostics, AASIST anti-spoofing, and ECAPA embedding.
    """
    import base64
    try:
        raw_bytes = base64.b64decode(req.audio_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 encoding")

    audio, orig_sr = load_audio_bytes(raw_bytes)
    audio_16k, diag = preprocess_for_speaker_model(audio, sample_rate=orig_sr, tag="VALIDATE-DEBUG")

    # AASIST inference
    aasist_res = deepfake_detector.analyze(
        audio_16k,
        sample_rate=16000,
        speech_detected=True,
        min_required_samples=24000
    )

    # ECAPA embedding & self-similarity
    emb = speaker_verifier.extract_embedding(audio_16k, sample_rate=16000, tag="VALIDATE-ECAPA")
    norm = float(np.linalg.norm(emb)) if emb is not None else 0.0
    self_sim = float(np.dot(emb, emb)) if emb is not None else 0.0

    return {
        "sample_rate": diag.get("sample_rate", 16000),
        "duration": diag.get("duration", 0.0),
        "peak": diag.get("peak", 0.0),
        "rms": diag.get("rms", 0.0),
        "mean": diag.get("mean", 0.0),
        "clipping_percent": diag.get("clipping_pct", 0.0),
        "aasist_prediction": aasist_res.get("prediction"),
        "spoof_probability": aasist_res.get("spoof_probability"),
        "genuine_probability": aasist_res.get("genuine_probability"),
        "raw_score": aasist_res.get("score"),
        "ecapa_embedding_norm": round(norm, 4),
        "ecapa_self_similarity": round(self_sim, 4),
        "audio_diagnostics": diag,
        "aasist_anti_spoof": aasist_res,
        "speaker_verification": {
            "norm": round(norm, 4),
            "self_similarity": round(self_sim, 4)
        },
        "voice_clone_paradox": {
            "detected": (aasist_res.get("prediction") == "SPOOF" and self_sim >= 0.80)
        }
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


async def _broadcast_live_events(call_id: str, analysis: dict) -> None:
    """Keep AUDIO_ANALYSIS first for existing clients, then emit standardized events."""
    await manager.broadcast(call_id, analysis)
    data = analysis.get("data") or {}
    anti = (data.get("voice_authenticity") or {}).get("anti_spoof") or {}
    ecapa = data.get("speaker_verification") or data.get("speaker") or {}
    await manager.broadcast(call_id, ws_event("AUDIO_STATUS", call_id, {
        "speech_detected": data.get("speech_detected"),
        "sample_rate": 16000,
        "window_count": analysis.get("window_count"),
        "continuous_duration": analysis.get("continuous_duration"),
        "vad": data.get("vad"),
        "audio": data.get("audio"),
        "microphone_connected": True,
    }))
    await manager.broadcast(call_id, ws_event("AASIST_UPDATE", call_id, anti))
    await manager.broadcast(call_id, ws_event("ECAPA_UPDATE", call_id, ecapa))
    await manager.broadcast(call_id, ws_event("PROSODY_UPDATE", call_id, data.get("prosody") or {}))
    fused = data.get("fused_trust") or data.get("preliminary_trust") or {}
    await manager.broadcast(call_id, ws_event("TRUST_UPDATE", call_id, fused))


async def _run_semantic_pipeline(call_id: str) -> None:
    buf = stream_processor.call_buffers.get(call_id)
    if not buf or getattr(buf, "whisper_busy", False):
        return
    buf.whisper_busy = True
    try:
        transcript = await asyncio.to_thread(stream_processor.run_incremental_asr, call_id)
        if transcript:
            logger.info(f"[TRANSCRIPT_UPDATE_SENT] call_id={call_id} text=\"{transcript.get('text')}\"")
            await manager.broadcast(call_id, ws_event(
                "TRANSCRIPT_UPDATE",
                call_id,
                transcript,
                text=transcript.get("text"),
                full_text=transcript.get("full_text"),
                engine="whisper"
            ))
            gemini = await asyncio.to_thread(
                stream_processor.run_conversation_update,
                call_id,
                transcript.get("full_text") or "",
            )
            if gemini:
                logger.info(f"[GEMINI_UPDATE_SENT] call_id={call_id} engine={gemini.get('engine')} risk={gemini.get('risk_score')}")
                await manager.broadcast(call_id, ws_event(
                    "GEMINI_UPDATE",
                    call_id,
                    gemini,
                    engine=gemini.get("engine")
                ))
            last = buf.last_analysis or {}
            data = last.get("data") or {}
            fused = live_semantics.fuse_trust(
                buf,
                aasist=(data.get("voice_authenticity") or {}).get("anti_spoof") or {},
                ecapa=data.get("speaker_verification") or {},
                prosody=data.get("prosody") or {},
                speech_detected=bool(data.get("speech_detected")),
            )
            await manager.broadcast(call_id, ws_event("TRUST_UPDATE", call_id, fused))
            incidents = await asyncio.to_thread(stream_processor.maybe_incidents, call_id)
            for inc in incidents:
                await manager.broadcast(call_id, ws_event("INCIDENT_CREATED", call_id, inc))
            await asyncio.to_thread(stream_processor.persist_semantics, call_id)
    except Exception:
        import traceback
        traceback.print_exc()
        await manager.broadcast(call_id, ws_event("ERROR", call_id, {
            "status": "SEMANTIC_PIPELINE_ERROR",
            "message": "Whisper/Gemini pipeline failed; acoustic analysis continues.",
        }))
    finally:
        if buf:
            buf.whisper_busy = False


@app.post("/api/live/dump_buffer/{call_id}")
async def dump_live_buffer_endpoint(call_id: str):
    """Development-only endpoint to dump the active 16kHz audio buffer as a WAV file for inspection."""
    import tempfile
    out_dir = os.path.join(tempfile.gettempdir(), "voxguard_dumps")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{call_id}.wav")
    try:
        path = stream_processor.dump_buffer_wav(call_id, out_path)
        return {"status": "OK", "call_id": call_id, "wav_path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.websocket("/ws/call/{call_id}")
async def websocket_call_endpoint(websocket: WebSocket, call_id: str):
    await manager.connect(call_id, websocket)
    try:
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "call_id": call_id,
            "session_id": call_id,
            "status": "STREAM_ACTIVE",
            "timestamp": time.strftime("%H:%M:%S", time.gmtime())
        })
        while True:
            message = await websocket.receive()
            msg_type = message.get("type")

            if msg_type == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"]:
                raw_bytes = message["bytes"]
                analysis = stream_processor.process_chunk(call_id, raw_bytes)
                if analysis:
                    await _broadcast_live_events(call_id, analysis)
                    asyncio.create_task(_run_semantic_pipeline(call_id))

            elif "text" in message and message["text"]:
                data = message["text"]
                try:
                    payload = json.loads(data) if data.startswith("{") else {"action": data}
                except Exception:
                    payload = {"action": data}

                action = payload.get("type") or payload.get("action")

                if action == "START_AUDIO_STREAM":
                    sample_rate = int(payload.get("sample_rate", 48000))
                    channels = int(payload.get("channels", 1))
                    fmt = payload.get("format", "pcm_s16le")
                    claimed_speaker_id = payload.get("claimed_speaker_id", "cfo_arun")
                    stream_processor.start_call_stream(
                        call_id,
                        sample_rate=sample_rate,
                        channels=channels,
                        format=fmt,
                        claimed_speaker_id=claimed_speaker_id
                    )
                    await websocket.send_json({
                        "type": "AUDIO_STREAM_STARTED",
                        "call_id": call_id,
                        "sample_rate": sample_rate,
                        "channels": channels,
                        "claimed_speaker_id": claimed_speaker_id,
                        "window_seconds": 3.0
                    })
                    await websocket.send_json(ws_event("SESSION_STARTED", call_id, {
                        "source": "REAL",
                        "status": "LIVE",
                        "sample_rate": sample_rate,
                        "channels": channels,
                        "claimed_speaker_id": claimed_speaker_id,
                    }))

                elif action == "SET_CLAIMED_SPEAKER":
                    claimed_speaker_id = payload.get("claimed_speaker_id", "cfo_arun")
                    stream_processor.set_claimed_speaker(call_id, claimed_speaker_id)
                    await websocket.send_json({
                        "type": "CLAIMED_SPEAKER_UPDATED",
                        "call_id": call_id,
                        "claimed_speaker_id": claimed_speaker_id
                    })

                elif action == "SET_CONTEXT":
                    ctx = stream_processor.apply_context(
                        call_id,
                        payload.get("data") or payload,
                        source=payload.get("source", "DEMO_CONTEXT"),
                    )
                    await manager.broadcast(call_id, ws_event("CONTEXT_UPDATE", call_id, ctx))

                elif action == "STOP_AUDIO_STREAM":
                    summary = stream_processor.stop_call_stream(call_id)
                    try:
                        await websocket.send_json({
                            "type": "AUDIO_STREAM_STOPPED",
                            "call_id": call_id,
                            "summary": summary
                        })
                        await websocket.send_json({
                            "type": "CALL_FINALIZED",
                            "call_id": call_id,
                            "summary": summary
                        })
                        await websocket.send_json(ws_event("SESSION_FINALIZED", call_id, summary or {}))
                    except Exception:
                        pass

                elif action == "PING":
                    await websocket.send_json({
                        "type": "PONG",
                        "timestamp": time.time()
                    })

                elif action == "TRIGGER_SCENARIO":
                    scenario_key = payload.get("scenario", "clone")
                    steps = demo.SCENARIOS_DATA.get(scenario_key, demo.SCENARIOS_DATA["clone"])["steps"]
                    for step in steps:
                        await manager.broadcast(call_id, {
                            "type": "TRUST_UPDATE",
                            "call_id": call_id,
                            "mode": "DEMO",
                            "data": step
                        })
                        await asyncio.sleep(1.5)

                elif action == "BLOCK_TRANSACTION":
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
        pass
    except RuntimeError as e:
        if "Cannot call" in str(e) or "close message has been sent" in str(e):
            pass
        else:
            import traceback
            traceback.print_exc()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        stream_processor.stop_call_stream(call_id)
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
