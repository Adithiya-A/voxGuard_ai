"""
VoxGuard AI — Database Module
Provides local persistent SQLite storage for enrolled speakers and real live call sessions.
"""

from backend.database.db import get_db_connection, init_db
from backend.database.repositories import speaker_repo, call_repo, incident_repo

__all__ = ["get_db_connection", "init_db", "speaker_repo", "call_repo", "incident_repo"]
