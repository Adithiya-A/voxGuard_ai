"""Live-session Whisper, Gemini, trust fusion, and incident helpers.

These run off the WebSocket receive loop (via asyncio.to_thread) so PCM ingest stays responsive.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from backend.database.repositories import call_repo, incident_repo
from backend.intelligence.context import context_engine, empty_session_context
from backend.intelligence.conversation import conversation_intelligence
from backend.models.transcription import transcription_service
from backend.services.firebase_sync import sync_call, sync_incident
from backend.trust.scoring import trust_engine

logger = logging.getLogger("voxguard.live_semantics")

MIN_ASR_SECONDS = 2.0
MAX_ASR_SECONDS = 5.0
GEMINI_MIN_NEW_CHARS = 40
GEMINI_MIN_INTERVAL_S = 2.0


def init_session_fields(buf) -> None:
    if getattr(buf, "_semantics_ready", False):
        return
    buf.processed_audio_position = 0
    buf.full_transcript = ""
    buf.last_transcript_piece = ""
    buf.transcript_history: List[Dict[str, Any]] = []
    buf.conversation_analysis: Optional[Dict[str, Any]] = None
    buf.last_gemini_text_len = 0
    buf.last_gemini_at = 0.0
    buf.session_context = empty_session_context()
    buf.caller_eval = context_engine.evaluate_caller()
    buf.transaction_eval = context_engine.evaluate_transaction()
    buf.incidents: List[Dict[str, Any]] = []
    buf.incident_keys = set()
    buf.whisper_busy = False
    buf.last_fused_trust: Optional[Dict[str, Any]] = None
    buf.last_asr_status: Optional[str] = None
    buf._semantics_ready = True


def append_transcript(previous: str, incoming: str) -> str:
    prev = (previous or "").strip()
    new = (incoming or "").strip()
    if not new:
        return prev
    if not prev:
        return new
    if new.lower() in prev.lower():
        return prev
    if prev.lower() in new.lower():
        return new
    max_ol = min(len(prev), len(new), 120)
    for n in range(max_ol, 12, -1):
        if prev[-n:].lower() == new[:n].lower():
            return (prev + new[n:]).strip()
    return f"{prev} {new}".strip()


def incremental_asr(buf) -> Optional[Dict[str, Any]]:
    """Transcribe only new 16 kHz speech. Never uses demo scripts."""
    init_session_fields(buf)
    audio = buf.continuous_16k
    if audio is None or len(audio) == 0:
        return None
    start = int(buf.processed_audio_position)
    if start < 0:
        start = 0
    if start >= len(audio):
        return None
    available = len(audio) - start
    min_samples = int(16000 * MIN_ASR_SECONDS)
    if available < min_samples:
        return None

    take = min(available, int(16000 * MAX_ASR_SECONDS))
    segment = np.asarray(audio[start:start + take], dtype=np.float32)
    result = transcription_service.transcribe_audio(segment, sample_rate=16000)
    buf.processed_audio_position = start + take
    buf.last_asr_status = result.get("status")

    text = (result.get("text") or "").strip()
    if result.get("status") in ("WHISPER_UNAVAILABLE", "MODEL_ERROR"):
        return {
            "text": "",
            "full_text": buf.full_transcript,
            "language": result.get("language"),
            "is_final": False,
            "timestamp": time.time(),
            "status": result.get("status"),
            "error": result.get("error"),
            "inference_ms": result.get("inference_ms", 0.0),
            "model": result.get("model", "faster-whisper"),
        }

    if not text:
        return None

    new_full = append_transcript(buf.full_transcript, text)
    if new_full == buf.full_transcript:
        return None

    piece = new_full[len(buf.full_transcript):].strip() or text
    buf.full_transcript = new_full
    buf.last_transcript_piece = piece
    entry = {
        "timestamp": time.strftime("%H:%M:%S", time.gmtime()),
        "speaker": "Caller",
        "text": piece,
        "flagged": conversation_intelligence.contains_high_risk_phrase(piece),
    }
    buf.transcript_history.append(entry)
    try:
        call_repo.save_transcript(buf.call_id, piece, new_full, result.get("language"), True)
        call_repo.save_timeline_event(buf.call_id, {
            "time": entry["timestamp"],
            "score": (buf.last_fused_trust or {}).get("trust_score", 85),
            "label": f"Transcript: {piece[:120]}",
            "type": "info",
        })
    except Exception as e:
        logger.warning(f"[ASR] Persist transcript failed: {e}")

    return {
        "text": piece,
        "full_text": new_full,
        "language": result.get("language") or "en",
        "is_final": True,
        "timestamp": time.time(),
        "status": result.get("status", "OK"),
        "inference_ms": result.get("inference_ms", 0.0),
        "model": result.get("model", "faster-whisper"),
        "duration": result.get("duration", 0.0),
        "segments": result.get("segments") or [],
    }


def should_run_gemini(buf, full_text: str) -> bool:
    text = (full_text or "").strip()
    if len(text) < 8:
        return False
    new_chars = len(text) - int(buf.last_gemini_text_len or 0)
    elapsed = time.time() - float(buf.last_gemini_at or 0.0)
    high_risk = conversation_intelligence.contains_high_risk_phrase(text[max(0, len(text) - 200):])
    return new_chars >= GEMINI_MIN_NEW_CHARS or elapsed >= 5.0 or (high_risk and elapsed >= GEMINI_MIN_INTERVAL_S)


def run_gemini(buf, full_text: str, force: bool = False) -> Optional[Dict[str, Any]]:
    init_session_fields(buf)
    text = (full_text or buf.full_transcript or "").strip()
    if not force and not should_run_gemini(buf, text):
        return None
    analysis = conversation_intelligence.analyze_transcript(text)
    buf.conversation_analysis = analysis
    buf.last_gemini_text_len = len(text)
    buf.last_gemini_at = time.time()
    try:
        call_repo.save_conversation_analysis(buf.call_id, analysis)
    except Exception as e:
        logger.warning(f"[GEMINI] Persist failed: {e}")
    return analysis


def apply_context(buf, updates: Dict[str, Any], source: str = "DEMO_CONTEXT") -> Dict[str, Any]:
    init_session_fields(buf)
    ctx = context_engine.merge_session_context(buf.session_context, updates, source=source)
    buf.session_context = ctx
    buf.caller_eval = context_engine.evaluate_caller(
        caller_number=ctx.get("caller_number"),
        known_contact=ctx.get("known_contact"),
        claimed_identity=ctx.get("claimed_identity"),
        contact_history=ctx.get("contact_history"),
        source=source,
    )
    new_ben = None
    if ctx.get("beneficiary"):
        new_ben = str(ctx.get("beneficiary")).lower() in ("new_account", "new", "true", "unknown")
    buf.transaction_eval = context_engine.evaluate_transaction(
        amount=ctx.get("transaction_amount"),
        currency=ctx.get("transaction_currency"),
        new_beneficiary=new_ben,
        beneficiary_name=ctx.get("beneficiary") if isinstance(ctx.get("beneficiary"), str) else None,
        transaction_type=ctx.get("transaction_type"),
        source=source,
    )
    try:
        call_repo.save_context(buf.call_id, {"session": ctx, "caller": buf.caller_eval, "transaction": buf.transaction_eval}, source)
    except Exception as e:
        logger.warning(f"[CONTEXT] Persist failed: {e}")
    return {
        "session": ctx,
        "caller": buf.caller_eval,
        "transaction": buf.transaction_eval,
        "source": source,
        "label": ctx.get("label"),
    }


def fuse_trust(buf, aasist: Dict[str, Any], ecapa: Dict[str, Any], prosody: Dict[str, Any], speech_detected: bool) -> Dict[str, Any]:
    init_session_fields(buf)
    aasist_final = aasist.get("prediction") == "SPOOF" and aasist.get("status") == "OK"
    ecapa_final = ecapa.get("status") == "MATCH"
    paradox = bool(aasist_final and ecapa_final)
    fused = trust_engine.fuse_live_signals(
        aasist=aasist,
        ecapa=ecapa,
        prosody=prosody,
        gemini=buf.conversation_analysis,
        caller_context=buf.caller_eval,
        transaction_context=buf.transaction_eval,
        possible_voice_clone=paradox,
        speech_detected=speech_detected,
    )
    fused["possible_voice_clone"] = paradox
    if paradox:
        fused["voice_clone"] = {
            "possible_voice_clone": True,
            "severity": "CRITICAL",
            "reason": "Synthetic speech detected while claimed speaker identity matches enrolled voiceprint",
        }
    buf.last_fused_trust = fused
    return fused


def maybe_create_incidents(buf, aasist: Dict[str, Any], ecapa: Dict[str, Any]) -> List[Dict[str, Any]]:
    init_session_fields(buf)
    created: List[Dict[str, Any]] = []
    gemini = buf.conversation_analysis or {}
    trust = buf.last_fused_trust or {}
    paradox = bool(aasist.get("prediction") == "SPOOF" and aasist.get("status") == "OK" and ecapa.get("status") == "MATCH")
    score = int(trust.get("trust_score", 100) or 100)

    candidates = []
    if paradox:
        candidates.append(("VOICE_CLONE_IMPERSONATION", "CRITICAL", "Voice clone paradox", "Synthetic speech with matching enrolled identity"))
    if gemini.get("credential_request"):
        candidates.append(("CREDENTIAL_HARVESTING", "HIGH", "Credential harvesting", "Caller requested passwords, OTP, or authentication secrets"))
    if gemini.get("financial_request") and gemini.get("authority_impersonation"):
        candidates.append(("SOCIAL_ENGINEERING_TRANSFER", "HIGH", "Authority + financial request", "Claimed executive authority combined with a transfer request"))
    if int(gemini.get("risk_score") or 0) >= 80 and gemini.get("social_engineering"):
        candidates.append(("SOCIAL_ENGINEERING", "HIGH", "High conversational risk", gemini.get("reasoning") or "High social-engineering risk"))
    if score < 30:
        candidates.append(("LOW_TRUST", "CRITICAL", "Critical trust score", f"Fused trust score {score}/100"))

    for key, severity, title, desc in candidates:
        if key in buf.incident_keys:
            continue
        buf.incident_keys.add(key)
        incident_id = f"INC-{buf.call_id[-8:]}-{len(buf.incidents)+1:02d}"
        record = {
            "incident_id": incident_id,
            "call_id": buf.call_id,
            "severity": severity,
            "type": key,
            "title": title,
            "description": desc,
            "evidence": {
                "aasist": {k: aasist.get(k) for k in ("prediction", "status", "spoof_probability", "genuine_probability", "inference_ms", "model", "device")},
                "ecapa": {k: ecapa.get(k) for k in ("status", "similarity_pct", "threshold", "display_name")},
                "prosody": getattr(buf, "last_analysis", {}) and (buf.last_analysis.get("data") or {}).get("prosody"),
                "transcript": buf.full_transcript,
                "gemini": gemini,
                "context": {"session": buf.session_context, "caller": buf.caller_eval, "transaction": buf.transaction_eval},
            },
            "recommended_action": trust.get("recommended_action") or "WARN",
            "mode": "REAL" if str(buf.call_id).startswith("VS-LIVE-") else "DEMO",
        }
        try:
            incident_repo.create_incident(record)
        except Exception as e:
            logger.warning(f"[INCIDENT] SQLite write failed: {e}")
        try:
            sync_incident(incident_id, record)
        except Exception:
            pass
        buf.incidents.append(record)
        created.append(record)
        try:
            call_repo.save_timeline_event(buf.call_id, {
                "time": time.strftime("%H:%M:%S", time.gmtime()),
                "score": score,
                "label": f"INCIDENT {incident_id}: {title}",
                "type": "critical" if severity == "CRITICAL" else "warning",
            })
        except Exception:
            pass
    return created


def persist_live_telemetry(call_id: str, buf, extra: Optional[Dict[str, Any]] = None) -> None:
    telemetry = {
        "transcript": buf.full_transcript,
        "transcript_history": buf.transcript_history,
        "gemini": buf.conversation_analysis,
        "conversation": buf.conversation_analysis,
        "session_context": buf.session_context,
        "caller_context": buf.caller_eval,
        "transaction": buf.transaction_eval,
        "incidents": buf.incidents,
        "prosody": ((buf.last_analysis or {}).get("data") or {}).get("prosody"),
    }
    if extra:
        telemetry.update(extra)
    updates = {"telemetry_summary": telemetry}
    trust = buf.last_fused_trust or {}
    if trust:
        updates["trust_score"] = trust.get("trust_score")
        updates["trust_level"] = trust.get("risk_level")
        updates["security_decision"] = trust.get("recommended_action")
        updates["action"] = trust.get("recommended_action")
    try:
        call_repo.update_call_telemetry(call_id, updates)
    except Exception as e:
        logger.warning(f"[DB] live telemetry failed: {e}")
    try:
        sync_call(call_id, {"call_id": call_id, "mode": "REAL", "telemetry": telemetry, "trust": trust})
    except Exception:
        pass
