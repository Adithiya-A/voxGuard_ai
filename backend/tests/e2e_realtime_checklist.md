# VoxGuard AI — End-to-end live microphone checklist

This is a manual validation script. It does not invent transcripts or trust scores.

## Start

1. `python -m uvicorn backend.main:app --port 8000`
2. `cd frontend && npm run dev`
3. Open Live Call (`/live-call`)
4. Enroll a speaker if needed (`/enrollment`) — embeddings persist in SQLite
5. Select the enrolled speaker and click **START LIVE MICROPHONE**
6. Speak naturally for at least 5 seconds

## Expected WebSocket sequence

CONNECTION_ESTABLISHED → SESSION_STARTED → AUDIO_STATUS / AUDIO_ANALYSIS →
AASIST_UPDATE (NOT_ENOUGH_AUDIO until ~4.04s) → ECAPA_UPDATE (INCONCLUSIVE until 3 speech windows) →
PROSODY_UPDATE → TRANSCRIPT_UPDATE (real Whisper text) → GEMINI_UPDATE (semantic risk only) →
TRUST_UPDATE → optional INCIDENT_CREATED → STOP → SESSION_FINALIZED

## After stop

7. Call History (`mode=REAL`) shows `VS-LIVE-*` without a page refresh (polls every 4s)
8. Investigation shows persisted transcript, Gemini analysis, trust, timeline
9. Restart backend; enrolled speaker and completed call remain in SQLite
10. Attack Simulator remains DEMO and must not write REAL SQLite rows

## Limits

- Browser microphone is not a cellular intercept
- Gemini does not classify cloned audio (AASIST does)
- Firebase Admin syncs cloud documents only when credentials are set; live audio stays on WebSocket
