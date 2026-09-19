# VoxGuard AI — Final Real Device Verification Report

Project: **VoxGuard AI — Trust Every Voice**  
Team: **Ratchagan** | Problem Statement: **SIH26104**  
Title: **AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks**  
Validation Date: **September 19, 2026**  
Overall System Status: **BACKEND VERIFIED — BROWSER E2E PENDING**

---

## 1. Executive Status

As established by architectural verification guidelines, system verification is categorized into three levels:

* **LEVEL 1 (Unit & Component Tests):** **PASS (100%)** — 108 of 108 backend tests passing across all pipeline stages.
* **LEVEL 2 (Backend WebSocket & Audio Pipeline):** **PASS** — Real audio ingress, VAD, AASIST, ECAPA-TDNN, Prosody, Whisper ASR, and Trust Engine fully verified via automated WebSocket client without mocks or fake telemetry.
* **LEVEL 3 (Actual Desktop Browser Microphone):** **PENDING USER VERIFICATION** — Audio capture graph, PCM conversion, WebSocket protocol, and live UI telemetry are prepared and running. Awaiting actual desktop browser microphone activation in Chrome or Edge.

---

## 2. Real-Device Verification Matrix

| Test | Result | Evidence |
| :--- | :--- | :--- |
| **Backend health** | **PASS** | `GET /api/health` returns HTTP 200 with status `HEALTHY`; all models online (AASIST, ECAPA-TDNN, DSP VAD, Prosody, faster-whisper, Trust Engine, Blockchain Ledger). |
| **Frontend build** | **PASS** | `npm run build` completed cleanly with 0 errors (46 modules transformed, `dist/index.html` 1.16 kB, `dist/assets/index-BMt7TUr0.js` 410.77 kB). |
| **Backend tests** | **PASS** | `python -m pytest -q` executed **108 of 108 passed** (100% pass rate in 41.07s). |
| **Browser microphone permission** | **NOT TESTED** | Requires user gesture in desktop Chrome/Edge (`navigator.mediaDevices.getUserMedia`). Headless agents cannot access native host audio devices. |
| **Browser PCM capture** | **NOT TESTED** | Prepared in `LiveCall.jsx` using `AudioContext({ sampleRate: 16000 })`, `ScriptProcessorNode(4096, 1, 1)`, and `floatTo16BitPCM`. Ready for desktop test. |
| **WebSocket audio** | **PASS** | Verified via `test_realtime_data_flow.py`, `test_phase1_audio.py`, `test_phase3_speaker.py`, `test_phase4_realtime_intelligence.py`. Ingests binary PCM chunks and broadcasts standardized updates. |
| **VAD** | **PASS** | Real DSP energy/ZCR/SNR computation in `dsp_vad.analyze`. Voiced speech produces `speech_detected=True`; digital silence produces `speech_detected=False`. |
| **AASIST** | **PASS** | Real model inference via `AASIST.pth`. Correctly predicted `BONAFIDE` (4.4% spoof probability) on genuine speech fixture. Short/silence audio safely returns `INCONCLUSIVE`. |
| **ECAPA** | **PASS** | Pretrained SpeechBrain ECAPA-TDNN (`spkrec-ecapa-voxceleb`) extracts 192-d normalized embeddings; rolling centroid verification against enrolled profiles verified. |
| **Prosody** | **PASS** | Real DSP autocorrelation pitch tracking verified (F0 in Hz, pitch std, jitter %, shimmer %, cadence anomaly). Zero fake numbers. |
| **Whisper** | **PASS** | `Systran/faster-whisper-base` verified. Transcribed actual speech fixture (*"The birch canoe slid on the smooth planks."*) in background worker thread without blocking audio loop. |
| **Gemini** | **PASS** | `GEMINI_API_KEY` loaded; real `gemini-2.5-flash` API tested with minimal prompt ("OK", 2000ms latency) and live coercion transcript resulting in structured 98 risk score and detected manipulation signals without blocking audio loop. |
| **Trust Engine** | **PASS** | Dynamic multi-signal mathematical fusion verified. Voice Clone Paradox correctly drops trust score to 9 (`CRITICAL`, `BLOCK_TRANSACTION`). |
| **Incident engine** | **PASS** | Verified: `AASIST=SPOOF` + `ECAPA=MATCH` creates `INCIDENT_CREATED`. Inconclusive combinations safely suppress clone paradox alerts. |
| **SQLite persistence** | **PASS** | SQLite database at `backend/data/voxguard.db` actively persists `enrolled_speakers` (71 profiles) and `calls` (206 records). |
| **Call History** | **PASS** | `GET /api/calls?mode=REAL` serves persisted live calls with exact timestamps, duration, trust scores, and security actions. |
| **Investigation** | **PASS** | Verified real forensic data loading from SQLite via `GET /api/calls/{call_id}` and `GET /api/calls/{call_id}/timeline`. Hardcoded fallbacks eliminated. |
| **Speaker persistence** | **PASS** | 71 genuine enrolled speaker profiles rehydrated from SQLite on FastAPI startup. Biometric embeddings preserved across server restarts. |
| **Firebase** | **PASS** | Firebase Admin SDK initialized with service credentials (`status: "OK"`). Verified Firestore write/read/delete on test doc and verified real SQLite call synced to Firestore `calls` collection. |
| **Browser console** | **PASS** | Vite dev server running cleanly; HMR active; added structured diagnostic logs `[AUDIO_CAPTURE_STARTED]` and `[AUDIO_FRAME_SENT]`. |
| **End-to-end** | **PARTIAL** | Overall: **BACKEND VERIFIED — BROWSER E2E PENDING**. Level 1 and Level 2 are 100% verified. Level 3 is awaiting user microphone session in desktop browser. |

---

## 3. End-to-End Audio Chunk Path Trace

The following specifies the exact trace of an individual microphone audio chunk from capture to persistence:

```
[User Speaks into Desktop Microphone]
                │
                ▼
1. Browser Capture:
   - Function: startMicrophoneStream() in LiveCall.jsx (lines 285–373)
   - AudioContext Sample Rate: 16,000 Hz (or native browser clock 44.1k/48k)
   - Channels: 1 (Mono)
   - ScriptProcessorNode: bufferSize = 4096 samples
                │
                ▼
2. PCM Conversion:
   - Function: floatTo16BitPCM()
   - Format: Signed 16-bit little-endian PCM (pcm_s16le, Int16Array, 8,192 bytes per chunk)
                │
                ▼
3. Transport:
   - Protocol: WebSocket (/ws/call/{call_id}) via CallWebSocket.sendAudioChunk()
   - Handshake: START_AUDIO_STREAM control frame with sample rate and claimed speaker
                │
                ▼
4. Backend Ingress:
   - Handler: websocket_call_endpoint() in backend/main.py (lines 334–430)
   - Function: stream_processor.process_chunk(call_id, raw_bytes)
                │
                ▼
5. Buffering & Preprocessing:
   - Manager: CallAudioBuffer in backend/audio/stream_processor.py
   - Storage: Continuous raw float32 buffer + resampled continuous 16kHz stream
   - Window: 3.0s rolling window, 1.0s hop
                │
                ▼
6. Parallel / Cascaded Acoustic Feature Extraction:
   - DSP VAD: dsp_vad.analyze() -> speech_detected (RMS, ZCR, SNR)
   - Prosody DSP: prosody_analyzer.analyze() -> F0, jitter, shimmer
   - AASIST: deepfake_detector.analyze() on 64,600 samples (4.04s) continuous buffer
   - ECAPA-TDNN: speaker_verifier.extract_embedding() + multi-window centroid cosine similarity
                │
                ▼
7. Fast Broadcast:
   - Function: _broadcast_live_events()
   - Events Emitted: AUDIO_ANALYSIS, AUDIO_STATUS, AASIST_UPDATE, ECAPA_UPDATE, PROSODY_UPDATE, TRUST_UPDATE
                │
                ▼
8. Non-Blocking Semantic Intelligence:
   - Worker Thread (asyncio.to_thread): stream_processor.run_incremental_asr() -> faster-whisper-base
   - Event Emitted: TRANSCRIPT_UPDATE
   - Semantic Analysis: Heuristic NLP / Gemini -> GEMINI_UPDATE
   - Incident Detection: live_semantics.maybe_create_incidents() -> INCIDENT_CREATED (if clone paradox)
                │
                ▼
9. React UI Update:
   - Handler: handleLiveWsMessage() in LiveCall.jsx
   - Updates: Waveform, VAD badge, AASIST gauge, ECAPA similarity meter, Prosody metrics, Live transcript, Trust score
                │
                ▼
10. Call Finalization & Ledger Persistence:
    - User clicks "End Call" -> STOP_AUDIO_STREAM sent
    - Backend: stream_processor.stop_call_stream() computes multi-window aggregated metrics
    - Database: call_repo.finalize_call() writes full forensic record into SQLite (backend/data/voxguard.db)
```

---

## 4. Operational Troubleshooting & Verification Checklist

To complete the Level 3 real device verification on your machine:

1. **Access Web Application:**
   - Open Google Chrome or Microsoft Edge.
   - Navigate to: `http://127.0.0.1:5173/live`
2. **Open Browser Developer Tools:**
   - Press `F12` (or `Ctrl + Shift + I`) and switch to the **Console** tab.
3. **Initiate Microphone Session:**
   - Select an enrolled profile from the dropdown menu (or leave as Default).
   - Click **Start Live Microphone**.
   - Click **Allow** when the browser prompts for microphone permissions.
4. **Confirm Diagnostic Logs:**
   - Browser Console will display:
     `[LIVE-DATA] WebSocket connected for VS-LIVE-... Sending START_AUDIO_STREAM.`
     `[AUDIO_CAPTURE_STARTED] { sampleRate: 16000, channels: 1, format: "pcm_s16le", ... }`
     `[AUDIO_FRAME_SENT] { chunkIndex: 1, byteLength: 8192 }`
   - Backend terminal will log:
     `[AUDIO_BYTES_RECEIVED] VS-LIVE-...: bytes=8192 | BUFFER_DURATION=...s | Processing 3.00s window`
     `[PERF] VS-LIVE-...: VAD=...ms, Features=...ms, Prosody=...ms, AntiSpoof=...ms, Speaker=...ms, Total=...ms`
5. **Observe Real Speech Processing:**
   - Speak for 15–20 seconds: *"VoxGuard is analyzing this live voice call for security risks."*
   - Verify speech badge turns green (`SPEECH DETECTED`).
   - Verify Prosody shows real fundamental frequency ($F_0$ around 100–250 Hz for human voices).
   - Verify Whisper outputs the live transcript into the call log.
6. **Finalize and Verify Persistence:**
   - Click **End Call**.
   - Navigate to `http://127.0.0.1:5173/call-history` — your new `VS-LIVE-...` call will appear with `mode = REAL`.
   - Click on the call to inspect the full timeline in `http://127.0.0.1:5173/investigation`.
