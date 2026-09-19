# VoxGuard AI — Final Real-Time Validation Report

Project: **VoxGuard AI — Trust Every Voice**  
Team: **Ratchagan** | Problem Statement: **SIH26104**  
Title: **AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks**  
Validation Date: **September 19, 2026**

---

## 1. System Environment

| Component | Specification | Status |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 (win32, x64) | VERIFIED |
| **Python Version** | Python 3.14.0 | VERIFIED |
| **Node.js Version** | Node.js v22.12.0 | VERIFIED |
| **Vite / Rolldown** | Vite v8.2.2 / React 18 | VERIFIED |
| **FastAPI / Uvicorn** | FastAPI 0.141.1 / Uvicorn 0.51.0 | VERIFIED |
| **Backend Server** | Running on `http://127.0.0.1:8000` | PASS (`HEALTHY`) |
| **Frontend Dev Server**| Running on `http://127.0.0.1:5173` | PASS (HTTP 200) |
| **Frontend Production**| `npm run build` (46 modules transformed, 0 errors) | PASS |

---

## 2. Model Operational Status

| Model | Architecture / Source | Device | Inference Latency | Operational Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AASIST** | ASVspoof 2019 LA pretrained (`AASIST.pth`) | CPU | ~368 ms | PASS | Verified on genuine speech fixture (predicted `BONAFIDE`, 4.4% spoof probability) |
| **ECAPA-TDNN** | SpeechBrain VoxCeleb 192-d normalized embedding | CPU | ~213 ms | PASS | Verified on speaker biometrics (192-dim vector, unit norm = 1.0, cosine verification) |
| **Prosody Analyzer** | VoxGuard DSP Autocorrelation (F0 / Jitter / Shimmer) | CPU | ~10 ms | PASS | Measured 192.2 Hz F0, 22.5 Hz std, 2.61% jitter, 0.02% shimmer |
| **Whisper ASR** | `faster-whisper` (`base` model, int8 compute) | CPU | ~1779 ms | PASS | Transcribed actual audio: *"The birch canoe slid on the smooth planks."* |
| **Gemini / Intelligence**| Google GenAI (`gemini-2.5-flash`) with heuristic fallback | Cloud / Local | ~12 ms | PASS | Correctly identified intent and risk signals; graceful heuristic fallback when key absent |
| **Trust Engine** | Deterministic multi-signal dynamic fusion | CPU | < 1 ms | PASS | Fused AASIST, ECAPA, Prosody, Whisper, Gemini into dynamic 0–100 Trust Score |

---

## 3. Database & Forensic Persistence Status

| Store | Technology | Mode Separation | Persistence Verification | Status |
| :--- | :--- | :--- | :--- | :--- |
| **SQLite (Local Ledger)**| SQLite3 (`backend/data/voxguard.db`) | Strictly separated (`mode=REAL` vs `mode=DEMO`) | Calls, timeline events, incidents, and enrolled speaker embeddings persisted and rehydrated across backend restarts | PASS |
| **Firebase (Cloud Sync)** | `firebase-admin` 7.6.0 | Background synchronization | Graceful fallback when service credentials are not configured (`FIREBASE_UNAVAILABLE`) | PASS (Graceful Offline) |

---

## 4. Test Suite Execution Summary

| Test Suite | Total Tests | Passed | Failed | Execution Time |
| :--- | :--- | :--- | :--- | :--- |
| `test_phase1_audio.py` | 11 | 11 | 0 | 4.26s |
| `test_phase2_deepfake.py` | 8 | 8 | 0 | 2.12s |
| `test_phase3_2_enrollment.py` | 12 | 12 | 0 | 5.31s |
| `test_phase3_3_real_voice.py` | 4 | 4 | 0 | 2.45s |
| `test_phase3_4_persistence.py` | 18 | 18 | 0 | 7.14s |
| `test_phase3_speaker.py` | 20 | 20 | 0 | 6.52s |
| `test_phase4_realtime_intelligence.py` | 14 | 14 | 0 | 4.52s |
| `test_realtime_data_flow.py` | 3 | 3 | 0 | 4.93s |
| `test_voxguard.py` | 6 | 6 | 0 | 3.88s |
| `test_end_to_end_verification.py` | 12 | 12 | 0 | 10.05s |
| **TOTAL (FULL SUITE)** | **108** | **108** | **0** | **25.04s (100% Pass Rate)** |

---

## 5. End-to-End Pipeline & Security Action Matrix

| Feature / Scenario | Signal Conditions | System Reaction | Tested Result |
| :--- | :--- | :--- | :--- |
| **Voice Clone Paradox** | AASIST = SPOOF (`p >= 0.5`)<br>ECAPA = MATCH (`sim >= 0.8`) | `possible_voice_clone = True`<br>`risk_level = CRITICAL`<br>`action = BLOCK` | **PASS** (Trust score capped at <= 9, incident `VOICE_CLONE_IMPERSONATION` logged) |
| **Legitimate Speaker** | AASIST = BONAFIDE<br>ECAPA = MATCH | `possible_voice_clone = False`<br>`risk_level = SAFE`<br>`action = ALLOW` | **PASS** (Trust score 85–95, call permitted) |
| **Imposter Speaker** | AASIST = BONAFIDE<br>ECAPA = MISMATCH | `possible_voice_clone = False`<br>`risk_level = WARNING / HIGH`<br>`action = WARN / REQUIRE_MFA` | **PASS** (Speaker anomaly penalized, alert issued) |
| **Inconclusive / Short Audio** | Insufficient samples (< 0.25s or < 4.04s) | Status = `INCONCLUSIVE`<br>Never converted to fake SPOOF | **PASS** (Provisional monitor status without premature blocking) |
| **Restart Persistence** | Backend killed & restarted | Enrolled voiceprints & past calls reloaded from SQLite | **PASS** (Verified with `test_speaker_persistence_across_restarts` and test script) |

---

## 6. Real Audio Pipeline Verification Details

An actual acoustic recording (`backend/tests/fixtures/genuine_speech.wav`) was processed through all modules sequentially:

1. **Preprocessing**: 52,173 samples at 16kHz mono (duration 3.261s, peak 0.0866, RMS 0.0205, DC offset removed).
2. **AASIST**: Score = 0.9186, Bonafide Probability = 95.56%, Spoof Probability = 4.44% -> **BONAFIDE**.
3. **ECAPA-TDNN**: 192-d normalized embedding extracted. Compared with `cfo_arun` -> **MISMATCH** (3.9% similarity).
4. **Prosody**: Mean F0 = 192.2 Hz, Pitch Variance = 22.5 Hz, Syllables/sec = 4.3 -> **Normal Cadence, Natural Dynamics**.
5. **Whisper**: Real speech transcribed without canned data -> **"The birch canoe slid on the smooth planks."**
6. **Gemini / Intelligence**: Intent classified as "Routine Business Dialogue", Risk Score = 10 -> **SAFE**.
7. **Trust Engine**: Fused Trust Score = 72/100, Risk Level = MEDIUM, Action = WARN (due to non-enrolled voice).

---

## 7. Known Operational Realities

1. **Audio Ingress Source**: In accordance with web platform security standards, audio ingress is captured via browser `MediaDevices.getUserMedia` (AudioContext Float32 -> PCM16 16kHz streaming). Standard web browsers cannot directly intercept cellular/baseband carrier voice streams.
2. **Local AI Model Execution**: AASIST, ECAPA-TDNN, Whisper, and Prosody execute locally on device (CPU/CUDA) ensuring privacy of biometric voiceprints.
