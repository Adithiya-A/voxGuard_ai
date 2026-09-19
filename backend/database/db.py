import os
import sqlite3
import logging
from typing import Generator
from contextlib import contextmanager

logger = logging.getLogger("voxguard.database")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "voxguard.db")

def ensure_db_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    ensure_db_dir()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception as e:
        logger.warning(f"Failed to set PRAGMA for SQLite: {e}")
    return conn

@contextmanager
def get_db(db_path: str = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str = DB_PATH) -> None:
    """
    Initializes database schema with required tables:
    - enrolled_speakers
    - calls
    - call_timeline
    """
    ensure_db_dir()
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # 1. Enrolled Speakers Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enrolled_speakers (
                speaker_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Enrolled Executive',
                enrolled_fips TEXT,
                embedding TEXT, -- JSON serialized 192-dim float array
                embedding_dimension INTEGER NOT NULL DEFAULT 192,
                threshold REAL NOT NULL DEFAULT 0.80,
                model TEXT NOT NULL DEFAULT 'speechbrain/spkrec-ecapa-voxceleb',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_synthetic INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ENROLLED'
            );
        """)

        # 2. Calls Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY,
                source TEXT NOT NULL DEFAULT 'LIVE_MICROPHONE', -- 'LIVE_MICROPHONE' | 'SIH_ATTACK_SIMULATOR'
                mode TEXT NOT NULL DEFAULT 'REAL',              -- 'REAL' | 'DEMO'
                status TEXT NOT NULL DEFAULT 'ACTIVE',          -- 'ACTIVE' | 'COMPLETED' | 'BLOCKED' | 'ERROR'
                claimed_speaker_id TEXT,
                claimed_speaker_name TEXT,
                caller TEXT DEFAULT 'Browser Microphone Stream',
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_seconds REAL DEFAULT 0.0,
                duration_formatted TEXT DEFAULT '00:00',
                sample_rate INTEGER DEFAULT 16000,
                channel_count INTEGER DEFAULT 1,
                trust_score INTEGER DEFAULT 85,
                trust_level TEXT DEFAULT 'SAFE',
                security_decision TEXT DEFAULT 'ALLOW',
                action TEXT DEFAULT 'ALLOW',
                anti_spoof_prediction TEXT DEFAULT 'INCONCLUSIVE',
                spoof_probability REAL,
                genuine_probability REAL,
                raw_anti_spoof_score REAL,
                speaker_status TEXT DEFAULT 'INCONCLUSIVE',
                speaker_similarity REAL DEFAULT 0.0,
                speaker_threshold REAL DEFAULT 0.80,
                speaker_windows INTEGER DEFAULT 0,
                total_windows INTEGER DEFAULT 0,
                speech_windows INTEGER DEFAULT 0,
                possible_voice_clone INTEGER DEFAULT 0,
                telemetry_summary TEXT, -- Compact JSON summary of telemetry
                timeline_json TEXT      -- Compact JSON array of session events
            );
        """)

        # 3. Call Timeline Events Table (optional fine-grained timeline)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                score INTEGER NOT NULL,
                label TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'info',
                created_at TEXT NOT NULL,
                FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE CASCADE
            );
        """)

        conn.commit()
        logger.info(f"[DB] Initialized database at {db_path}")

get_db_connection = get_connection
