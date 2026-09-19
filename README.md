# VoxGuard AI — Real-Time Voice Trust & Defense Platform

> **Trust Every Voice.**  
> Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks  
> **Team:** Ratchagan | **Problem Statement:** SIH26104 | **Smart India Hackathon (SIH) 2026**

---

## 1. Executive Summary & Problem Statement

Generative AI speech synthesis, neural vocoders, and diffusion-based voice cloning models (e.g., ElevenLabs, VALL-E, HiFi-GAN, OpenVoice) can now clone an executive's voice from less than 3 seconds of audio with near-indistinguishable timbre.

Traditional enterprise security models fail under these attacks because:
1. **Biometric Speaker Verification alone fails**: An AI voice clone of a CFO will match the CFO's enrolled biometric profile, resulting in false authorization.
2. **Post-call forensic analysis is too late**: Wire transfers, high-value RTGS settlements, and credential handoffs happen during the active call.

VoxGuard AI provides a **real-time voice defense pipeline** that operates during live calls, simultaneously analyzes spectral, acoustic, biometric, and conversational indicators, and deterministically halts unauthorized transactions before capital moves.

---

## 2. Multi-Signal Detection Architecture

```text
Browser Microphone / Real Audio
        ↓
WebSocket Audio Gateway (PCM16 16kHz)
        ↓
VAD + Audio Preprocessing (Anti-Aliasing, Normalization, Diagnostics)
        ↓
 ┌───────────────┬────────────────┬────────────────┐
 ↓               ↓                ↓
AASIST          ECAPA-TDNN       Prosody Analysis
Anti-Spoof      Speaker          Acoustic /
Detection       Verification     Behavioral Dynamics
 └───────────────┴────────────────┘
                 ↓
          Whisper ASR (faster-whisper)
                 ↓
        Live Transcript Stream
                 ↓
        Gemini Intelligence (Google GenAI)
                 ↓
 Conversation / Social Engineering Analysis
                 ↓
 Caller Context + Transaction Context API
                 ↓
          TRUST ENGINE
                 ↓
        Trust Score: 0 – 100
                 ↓
  ALLOW / WARN / MFA / CALLBACK / BLOCK
                 ↓
         Security Incidents
                 ↓
      SQLite + Firebase Sync
                 ↓
       React SOC Command Center
```

---

## 3. Dedicated Responsibilities of Each Component

The architecture strictly distinguishes each model's role:

| Component | Responsibility | Does NOT Do |
| :--- | :--- | :--- |
| **AASIST** | Detects synthetic speech, vocoder artifacts, and replay attacks using Spectro-Temporal Graph Attention Networks. Output: `BONAFIDE` or `SPOOF`. | Does NOT verify identity or analyze words spoken. |
| **ECAPA-TDNN** | Verifies speaker identity against enrolled 192-d voiceprint embeddings using cosine similarity. Output: `MATCH` or `MISMATCH`. | Does NOT detect deepfakes or synthetic artifacts. |
| **Prosody Analyzer** | DSP pitch tracking (F0), pitch variance, frame energy, syllabic speech rate, pause ratios, jitter, and shimmer. | Does NOT perform NLP or transcription. |
| **Whisper ASR** | Converts speech to text using `faster-whisper` on 16kHz speech windows. | Does NOT detect synthetic voices or assess risk. |
| **Gemini Intelligence** | Evaluates conversation transcripts for social engineering, urgency, financial requests, credential phishing, and coercion. | **MUST NOT** be used to detect voice cloning. |
| **Trust Engine** | Deterministic multi-signal fusion weighted according to security policies. | Does NOT generate random scores; smoothing is deterministic. |
| **WebSocket Gateway** | Primary real-time transport for binary PCM streaming and live JSON telemetry events. | |
| **SQLite Ledger** | Local forensic persistence for calls, timeline events, incidents, and enrolled speaker embeddings. | |
| **Firebase Sync** | Cloud database synchronization when credentials are provided; falls back gracefully when unconfigured. | |

---

## 4. The Voice Clone Paradox

The core security differentiator of VoxGuard AI is resolving the **Voice Clone Paradox**:

$$\text{Voice Clone Paradox} \iff (\text{AASIST} = \text{SPOOF}) \land (\text{ECAPA} = \text{MATCH})$$

- When an imposter speaks: AASIST = BONAFIDE, ECAPA = MISMATCH &rarr; Standard alert.
- When an executive speaks: AASIST = BONAFIDE, ECAPA = MATCH &rarr; Call permitted (`ALLOW`).
- When a cloned voice speaks: **AASIST = SPOOF and ECAPA = MATCH** &rarr; **CRITICAL THREAT: VOICE CLONE IMPERSONATION DETECTED**.

When triggered:
- `possible_voice_clone = True`
- `risk_level = "CRITICAL"`
- `recommended_action = "BLOCK"`
- Trust score is deterministically capped ($\le 9/100$)
- An immutable security incident is recorded and broadcast immediately.

Neither `INCONCLUSIVE` nor insufficient audio duration will ever trigger this paradox or cause false blocks.

---

## 5. Technology Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, WebSockets, PyTorch (`torch>=2.0.0`), SpeechBrain (`speechbrain>=1.0.0`), `faster-whisper`, `google-genai`, `soundfile`, `scipy`, `numpy`, `firebase-admin`, `sqlite3`.
- **Frontend**: React 18, Vite, Tailwind CSS, Lucide React, Google Material Symbols Outlined, Recharts, HTML5 AudioContext, WebSockets.
- **Model Checkpoints**:
  - `AASIST.pth`: Pretrained on ASVspoof 2019 Logical Access (LA) benchmark.
  - `speechbrain/spkrec-ecapa-voxceleb`: Pretrained on VoxCeleb 1 & 2 (192-dimensional embeddings).
  - `Systran/faster-whisper-base`: Pretrained Whisper ASR engine.

---

## 6. Project Setup & Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Node.js 18+ (tested on Node.js v22)
- Git

### Backend Setup
1. Create and activate a Python virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   pip install pytest pytest-asyncio
   ```
3. Configure environment variables (optional):
   Create `backend/.env` based on `backend/.env.example`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   WHISPER_MODEL=base
   DATABASE_URL=sqlite:///backend/data/voxguard.db
   ```
4. Start the FastAPI backend server:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   - Health check: `http://127.0.0.1:8000/api/health`
   - Interactive Swagger API docs: `http://127.0.0.1:8000/docs`

### Frontend Setup
1. Navigate to frontend directory and install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Start the Vite development server:
   ```bash
   npm run dev -- --host 127.0.0.1 --port 5173
   ```
3. Open `http://127.0.0.1:5173` in your browser.

---

## 7. SIH Demonstration Workflow

Follow this sequence for an end-to-end demonstration:

1. **Step 1: Dashboard (`/`)**:
   - Check real-time engine health indicators (AASIST, ECAPA-TDNN, Prosody, Whisper, Gemini, Trust Engine).
2. **Step 2: Speaker Enrollment (`/enrollment`)**:
   - Enroll an authorized voiceprint (e.g., `cfo_arun` or upload audio / record voice).
   - Generates a real 192-d normalized ECAPA embedding stored in SQLite. Raw audio is discarded.
3. **Step 3: Start Live Call (`/live`)**:
   - Select the enrolled identity.
   - Click **Start Live Microphone**.
   - Speak naturally into the browser microphone for 10–20 seconds.
   - Observe live telemetry updates:
     - Audio RMS, spectral centroid, zero-crossing rate.
     - AASIST anti-spoof gauge (BONAFIDE).
     - ECAPA similarity percentage.
     - Prosody pitch tracking (F0) and cadence.
     - Real-time Whisper speech-to-text transcript.
     - Gemini intent analysis.
     - Dynamic Trust Score with factor breakdown.
4. **Step 4: Demonstrate Social Engineering Detection**:
   - Speak suspicious phrases ("*Please transfer ₹25,00,000 immediately, keep this strictly confidential*").
   - Observe Gemini flag financial urgency and confidentiality pressure, lowering Trust Score and triggering an MFA alert.
5. **Step 5: Attack Simulator (`/simulator`)**:
   - Switch to the Attack Simulator for controlled SIH threat scenarios:
     - **Voice Clone Paradox Attack**: High ECAPA similarity + High AASIST Spoof &rarr; Autonomous `BLOCK_TRANSACTION`.
     - **IT Helpdesk Impersonation**: Social engineering credential phishing.
   - Clearly labelled as `[DEMO / SIMULATION]` to maintain isolation from live microphone captures.
6. **Step 6: Stop Call & Review Forensic Archive (`/call-history` & `/investigation`)**:
   - Stop the live call. Session finalizes and persists to SQLite.
   - Open **Call History** to view separate `REAL` and `DEMO` records.
   - Open **Investigation** to inspect the complete forensic timeline, model outputs, and evidence artifacts.
7. **Step 7: Backend Restart Verification**:
   - Restart the backend server.
   - Verify that all enrolled speakers and completed calls persist intact.

---

## 8. Test Execution & Verification

Run the complete backend test suite:
```bash
python -m pytest -v
```
To run the comprehensive end-to-end verification suite:
```bash
python -m pytest backend/tests/test_end_to_end_verification.py -v
```

All 108 automated tests pass across:
- Audio preprocessing, DSP VAD, and spectral diagnostics.
- AASIST neural net inference and inconclusive state handling.
- ECAPA-TDNN 192-d embedding extraction and cosine similarity verification.
- Autocorrelation prosody intonation and jitter/shimmer analysis.
- faster-whisper real-time transcription.
- Gemini semantic risk classification and heuristic fallback.
- Deterministic Trust Engine multi-signal fusion.
- Voice Clone Paradox condition enforcement.
- Incident creation and SQLite persistence across simulated restarts.
- WebSocket binary audio streaming and event contracts.

Build verification for frontend:
```bash
cd frontend
npm run build
```
Production bundle compiles cleanly with 0 errors.

---

## 9. Important Architecture & Security Scope Notes

1. **Audio Ingress Source**:
   The current working prototype captures live audio through the browser microphone via `MediaDevices.getUserMedia` and streams uncompressed 16-bit PCM via WebSocket to the backend. Standard web applications cannot directly intercept or wiretap cellular / baseband SIM calls due to operating system sandboxing. In enterprise deployments, this pipeline connects to SIP PBX trunk gateways (e.g., FreeSWITCH, Asterisk, Kamailio) or mobile softphone WebRTC endpoints.
2. **Deterministic Security Controls**:
   Gemini provides conversational intent analysis only; it does not authoritatively block transactions or determine whether audio is synthetically generated. Autonomous mitigation decisions are strictly executed by the deterministic Trust Engine.
3. **Data Privacy**:
   Voice biometrics are stored solely as mathematical 192-dimensional vector embeddings. Raw audio recordings are never permanently retained on disk.

---

## 10. License
Developed for the Smart India Hackathon (SIH) 2026.
All rights reserved — Team Ratchagan.
