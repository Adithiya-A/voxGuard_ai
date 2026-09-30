import json
import time
import logging
from typing import List, Optional, Dict, Any

from backend.database.db import get_db, DB_PATH
from backend.database.models import SpeakerRecord, CallRecord

logger = logging.getLogger("voxguard.database")

class SpeakerRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_speaker(self, speaker_id: str) -> Optional[SpeakerRecord]:
        clean_id = (speaker_id or "").strip().lower()
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM enrolled_speakers WHERE LOWER(speaker_id) = ?;", (clean_id,))
            row = cursor.fetchone()
            if row:
                return SpeakerRecord.from_row(row)
        return None

    def list_speakers(self, include_synthetic: bool = True) -> List[SpeakerRecord]:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            if include_synthetic:
                cursor.execute("SELECT * FROM enrolled_speakers ORDER BY created_at ASC;")
            else:
                cursor.execute("SELECT * FROM enrolled_speakers WHERE is_synthetic = 0 ORDER BY created_at ASC;")
            rows = cursor.fetchall()
            return [SpeakerRecord.from_row(r) for r in rows]

    def save_speaker(self, record: SpeakerRecord) -> None:
        emb_str = json.dumps(record.embedding) if record.embedding is not None else None
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        created = record.created_at or now
        updated = now

        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO enrolled_speakers (
                    speaker_id, display_name, role, enrolled_fips,
                    embedding, embedding_dimension, threshold, model,
                    created_at, updated_at, is_synthetic, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(speaker_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    role = excluded.role,
                    enrolled_fips = excluded.enrolled_fips,
                    embedding = excluded.embedding,
                    embedding_dimension = excluded.embedding_dimension,
                    threshold = excluded.threshold,
                    model = excluded.model,
                    updated_at = excluded.updated_at,
                    is_synthetic = excluded.is_synthetic,
                    status = excluded.status;
            """, (
                record.speaker_id,
                record.display_name,
                record.role,
                record.enrolled_fips,
                emb_str,
                record.embedding_dimension,
                record.threshold,
                record.model,
                created,
                updated,
                1 if record.is_synthetic else 0,
                record.status
            ))
            conn.commit()
            logger.info(f"[DB] Saved speaker: {record.speaker_id} ({record.display_name})")

    def delete_speaker(self, speaker_id: str) -> bool:
        clean_id = (speaker_id or "").strip().lower()
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM enrolled_speakers WHERE LOWER(speaker_id) = ?;", (clean_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info(f"[DB] Deleted speaker: {clean_id}")
            return deleted


class CallRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def save_call(self, record: CallRecord) -> CallRecord:
        return self.create_call(record=record)

    def create_call(self, record: Optional[CallRecord] = None, **kwargs) -> CallRecord:
        if record is None:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            record = CallRecord(
                call_id=kwargs.get("call_id", f"VS-LIVE-{int(time.time())}"),
                mode=kwargs.get("mode", "REAL"),
                caller=kwargs.get("caller", "Microphone Ingress"),
                claimed_speaker_name=kwargs.get("claimed_identity") or kwargs.get("claimed_speaker_name"),
                claimed_speaker_id=kwargs.get("claimed_speaker_id", "cfo_arun"),
                started_at=kwargs.get("started_at", now),
                status=kwargs.get("status", "ACTIVE"),
                trust_score=kwargs.get("trust_score", 85)
            )

        telemetry_str = json.dumps(record.telemetry_summary) if record.telemetry_summary else None
        timeline_str = json.dumps(record.timeline) if record.timeline else None

        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO calls (
                    call_id, source, mode, status,
                    claimed_speaker_id, claimed_speaker_name, caller,
                    started_at, ended_at, duration_seconds, duration_formatted,
                    sample_rate, channel_count, trust_score, trust_level,
                    security_decision, action, anti_spoof_prediction,
                    spoof_probability, genuine_probability, raw_anti_spoof_score,
                    speaker_status, speaker_similarity, speaker_threshold,
                    speaker_windows, total_windows, speech_windows,
                    possible_voice_clone, telemetry_summary, timeline_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                record.call_id,
                record.source,
                record.mode,
                record.status,
                record.claimed_speaker_id,
                record.claimed_speaker_name,
                record.caller,
                record.started_at,
                record.ended_at,
                record.duration_seconds,
                record.duration_formatted,
                record.sample_rate,
                record.channel_count,
                record.trust_score,
                record.trust_level,
                record.security_decision,
                record.action,
                record.anti_spoof_prediction,
                record.spoof_probability,
                record.genuine_probability,
                record.raw_anti_spoof_score,
                record.speaker_status,
                record.speaker_similarity,
                record.speaker_threshold,
                record.speaker_windows,
                record.total_windows,
                record.speech_windows,
                1 if record.possible_voice_clone else 0,
                telemetry_str,
                timeline_str
            ))
            conn.commit()
            logger.info(f"[DB] Created call session: {record.call_id} (mode={record.mode}, status={record.status})")
            return record

    def update_call_telemetry(self, call_id: str, updates: Dict[str, Any]) -> None:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            fields = []
            values = []

            for key, val in updates.items():
                if key in ("telemetry_summary", "timeline_json") and isinstance(val, (dict, list)):
                    val = json.dumps(val)
                elif key == "possible_voice_clone":
                    val = 1 if val else 0
                fields.append(f"{key} = ?")
                values.append(val)

            if not fields:
                return

            values.append(call_id)
            query = f"UPDATE calls SET {', '.join(fields)} WHERE call_id = ?;"
            cursor.execute(query, tuple(values))
            conn.commit()

    def finalize_call(self, call_id: str, summary: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[CallRecord]:
        """
        Finalizes an active call, setting status = 'COMPLETED', ended_at, duration, and final aggregated scores.
        """
        if summary is None:
            summary = kwargs
        else:
            summary = {**summary, **kwargs}

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        duration_sec = float(summary.get("duration_seconds", 0.0))
        mins = int(duration_sec // 60)
        secs = int(duration_sec % 60)
        formatted_dur = f"{mins:02d}:{secs:02d}"

        updates = {
            "status": "COMPLETED",
            "ended_at": now,
            "duration_seconds": duration_sec,
            "duration_formatted": formatted_dur,
            "trust_score": summary.get("trust_score", 85),
            "trust_level": summary.get("trust_level", "SAFE"),
            "security_decision": summary.get("security_decision", "ALLOW"),
            "action": summary.get("action", "ALLOW"),
            "anti_spoof_prediction": summary.get("anti_spoof_prediction", "INCONCLUSIVE"),
            "spoof_probability": summary.get("spoof_probability"),
            "genuine_probability": summary.get("genuine_probability"),
            "raw_anti_spoof_score": summary.get("raw_anti_spoof_score"),
            "speaker_status": summary.get("speaker_status", "INCONCLUSIVE"),
            "speaker_similarity": summary.get("speaker_similarity", 0.0),
            "speaker_windows": summary.get("speaker_windows", 0),
            "total_windows": summary.get("total_windows", 0),
            "speech_windows": summary.get("speech_windows", 0),
            "possible_voice_clone": 1 if summary.get("possible_voice_clone") else 0,
        }

        if "telemetry_summary" in summary:
            updates["telemetry_summary"] = json.dumps(summary["telemetry_summary"])
        if "timeline" in summary:
            updates["timeline_json"] = json.dumps(summary["timeline"])

        self.update_call_telemetry(call_id, updates)
        logger.info(f"[DB] Finalized call {call_id}: duration={formatted_dur}, trust={updates['trust_score']}, speaker={updates['speaker_status']}, aasist={updates['anti_spoof_prediction']}")
        try:
            from backend.services.firebase_sync import sync_call
            sync_call(call_id, {
                "call_id": call_id,
                "status": "COMPLETED",
                "duration_seconds": duration_sec,
                "duration_formatted": formatted_dur,
                "trust_score": updates["trust_score"],
                "trust_level": updates["trust_level"],
                "security_decision": updates["security_decision"],
                "anti_spoof_prediction": updates["anti_spoof_prediction"],
                "speaker_status": updates["speaker_status"],
                "speaker_similarity": updates["speaker_similarity"],
                "possible_voice_clone": bool(updates["possible_voice_clone"]),
                "telemetry_summary": summary.get("telemetry_summary")
            })
        except Exception:
            pass
        return self.get_call(call_id)

    def get_call(self, call_id: str) -> Optional[CallRecord]:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM calls WHERE call_id = ?;", (call_id,))
            row = cursor.fetchone()
            if row:
                return CallRecord.from_row(row)
        return None

    def list_calls(self, mode_filter: Optional[str] = None, limit: int = 100) -> List[CallRecord]:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            if mode_filter and mode_filter.upper() != "ALL":
                cursor.execute(
                    "SELECT * FROM calls WHERE UPPER(mode) = ? ORDER BY started_at DESC LIMIT ?;",
                    (mode_filter.upper(), limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM calls ORDER BY started_at DESC LIMIT ?;",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [CallRecord.from_row(r) for r in rows]

    def get_counts(self) -> Dict[str, int]:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM calls WHERE mode = 'REAL';")
            real_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM calls WHERE mode = 'REAL' AND status = 'COMPLETED';")
            real_completed = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM calls WHERE mode = 'REAL' AND possible_voice_clone = 1;")
            real_threats = cursor.fetchone()[0]
            return {
                "real_calls_total": real_count,
                "real_calls_completed": real_completed,
                "real_threats": real_threats
            }

    def save_timeline_event(self, call_id: str, event: Dict[str, Any]) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO call_timeline (call_id, timestamp, score, label, event_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    call_id,
                    event.get("time") or now,
                    int(event.get("score") or 0),
                    event.get("label") or "",
                    event.get("type") or "info",
                    now,
                ),
            )
            conn.commit()

    def append_timeline_event(self, call_id: str, event: Dict[str, Any]) -> None:
        self.save_timeline_event(call_id, event)

    def get_timeline(self, call_id: str) -> List[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM call_timeline WHERE call_id = ? ORDER BY id ASC;", (call_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "call_id": r["call_id"],
                    "timestamp": r["timestamp"],
                    "score": r["score"],
                    "label": r["label"],
                    "event_type": r["event_type"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def save_transcript(self, call_id: str, text: str, full_text: str, language: Optional[str], is_final: bool = True) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transcripts (call_id, text, full_text, language, is_final, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (call_id, text, full_text, language, 1 if is_final else 0, now),
            )
            conn.commit()

    def save_conversation_analysis(self, call_id: str, analysis: Dict[str, Any]) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversation_analysis (call_id, analysis_json, risk_score, created_at)
                VALUES (?, ?, ?, ?);
                """,
                (call_id, json.dumps(analysis), int(analysis.get("risk_score") or analysis.get("social_engineering_risk") or 0), now),
            )
            conn.commit()

    def save_context(self, call_id: str, context: Dict[str, Any], source: str = "DEMO_CONTEXT") -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO call_contexts (call_id, context_json, source, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(call_id) DO UPDATE SET
                    context_json = excluded.context_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at;
                """,
                (call_id, json.dumps(context), source, now),
            )
            conn.commit()

    def get_context(self, call_id: str) -> Optional[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT context_json, source FROM call_contexts WHERE call_id = ?;", (call_id,))
            row = cursor.fetchone()
            if not row:
                return None
            try:
                data = json.loads(row["context_json"])
            except Exception:
                data = {}
            data["source"] = row["source"]
            return data


class IncidentRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def create_incident(self, record: Dict[str, Any]) -> Dict[str, Any]:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record.setdefault("created_at", now)
        record.setdefault("status", "OPEN")
        record.setdefault("mode", "REAL")
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO incidents (
                    incident_id, call_id, severity, type, title, description,
                    evidence_json, recommended_action, status, mode, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record["incident_id"],
                    record["call_id"],
                    record.get("severity", "HIGH"),
                    record.get("type", "THREAT"),
                    record.get("title"),
                    record.get("description"),
                    json.dumps(record.get("evidence") or {}),
                    record.get("recommended_action"),
                    record.get("status", "OPEN"),
                    record.get("mode", "REAL"),
                    record.get("created_at", now),
                ),
            )
            conn.commit()
        return record

    def list_incidents(self, mode_filter: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            if mode_filter and mode_filter.upper() not in ("ALL", ""):
                cursor.execute(
                    "SELECT * FROM incidents WHERE UPPER(mode) = ? ORDER BY created_at DESC LIMIT ?;",
                    (mode_filter.upper(), limit),
                )
            else:
                cursor.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            out = []
            for row in rows:
                evidence = {}
                if row["evidence_json"]:
                    try:
                        evidence = json.loads(row["evidence_json"])
                    except Exception:
                        evidence = {}
                out.append({
                    "incident_id": row["incident_id"],
                    "call_id": row["call_id"],
                    "severity": row["severity"],
                    "type": row["type"],
                    "threat_type": row["type"],
                    "title": row["title"],
                    "threat_label": row["title"],
                    "description": row["description"],
                    "evidence": evidence,
                    "recommended_action": row["recommended_action"],
                    "status": row["status"],
                    "mode": row["mode"],
                    "created_at": row["created_at"],
                    "opened_at": row["created_at"],
                })
            return out

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        for inc in self.list_incidents(limit=1000):
            if inc["incident_id"] == incident_id:
                return inc
        return None


speaker_repo = SpeakerRepository()
call_repo = CallRepository()
incident_repo = IncidentRepository()
