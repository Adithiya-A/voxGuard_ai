import React, { useState, useEffect, useRef } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import { CallWebSocket } from '../services/websocket';
import TrustScoreGauge from '../components/trust/TrustScoreGauge';
import RiskBreakdown from '../components/trust/RiskBreakdown';
import SpectrogramView from '../components/voice/SpectrogramView';
import ActionModal from '../components/security/ActionModal';

export default function LiveCall() {
  const { triggerSecurityAction } = useApp();
  const location = useLocation();

  // Operational Mode: 'idle' | 'live' | 'demo'
  const [mode, setMode] = useState('idle');

  // Real Microphone Live Session State (Completely isolated from mock data)
  const emptyLive = {
    active: false,
    callId: null,
    source: 'REAL',
    status: 'IDLE',
    startedAt: null,
    endedAt: null,
    duration: 0,
    windows: 0,
    speechWindows: 0,
    latestAnalysis: null,
    history: [],
    aasist: null,
    ecapa: null,
    prosody: null,
    transcript: { text: '', full_text: '', language: null, status: null },
    gemini: null,
    context: null,
    trust: null,
    incidents: [],
    sampleRate: 16000,
  };

  const [liveSession, setLiveSession] = useState(emptyLive);
  const [completedSession, setCompletedSession] = useState(null);
  const [demoContextDraft, setDemoContextDraft] = useState({
    claimed_identity: '',
    caller_number: '',
    transaction_amount: '',
    transaction_currency: 'INR',
    transaction_type: 'bank_transfer',
    beneficiary: '',
  });

  // Streaming Hardware States: IDLE, CONNECTING, LISTENING, ANALYZING, STOPPING, ERROR
  const [streamStatus, setStreamStatus] = useState('IDLE');
  const [errorMessage, setErrorMessage] = useState('');
  const [chunksSent, setChunksSent] = useState(0);

  // Enrolled speaker reference options (Loaded dynamically from GET /api/speakers)
  const [enrolledSpeakersList, setEnrolledSpeakersList] = useState([
    { speaker_id: 'cfo_arun', display_name: 'CFO - Arun Sharma', role: 'Chief Financial Officer (Demo Reference)', is_synthetic: true },
    { speaker_id: 'vp_sarah', display_name: 'Sarah Jenkins - VP Treasury', role: 'VP Global Treasury (Demo Reference)', is_synthetic: true }
  ]);
  const [claimedSpeaker, setClaimedSpeaker] = useState('cfo_arun');

  // Fetch real enrolled speakers from backend
  useEffect(() => {
    const loadSpeakers = async () => {
      try {
        const list = await api.getSpeakers();
        if (Array.isArray(list) && list.length > 0) {
          setEnrolledSpeakersList(list);
          if (location.state?.selectedSpeakerId) {
            setClaimedSpeaker(location.state.selectedSpeakerId);
          } else {
            // Default to first real enrolled speaker if available
            const realSpeaker = list.find((s) => !s.is_synthetic);
            if (realSpeaker) {
              setClaimedSpeaker(realSpeaker.speaker_id);
            }
          }
        }
      } catch (err) {
        console.warn('[LIVE-DATA] Could not fetch enrolled speakers:', err);
      }
    };
    loadSpeakers();
  }, [location.state]);

  // Demo Simulation State (Isolated for SIH Attack Demonstration)
  const [demoCallData, setDemoCallData] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);
  const timerRef = useRef(null);

  const submitDemoContext = async () => {
    if (!liveSession.callId) return;
    const payload = {
      source: 'DEMO_CONTEXT',
      claimed_identity: demoContextDraft.claimed_identity || null,
      caller_number: demoContextDraft.caller_number || null,
      transaction_amount: demoContextDraft.transaction_amount ? Number(demoContextDraft.transaction_amount) : null,
      transaction_currency: demoContextDraft.transaction_currency || 'INR',
      transaction_type: demoContextDraft.transaction_type || null,
      beneficiary: demoContextDraft.beneficiary || null,
    };
    try {
      const data = await api.setCallContext(liveSession.callId, payload);
      setLiveSession((prev) => ({ ...prev, context: data }));
      if (wsRef.current && wsRef.current.isOpen()) {
        wsRef.current.sendControl({ type: 'SET_CONTEXT', source: 'DEMO_CONTEXT', data: payload });
      }
    } catch (e) {
      setErrorMessage('Failed to persist DEMO_CONTEXT');
    }
  };

  const handleClaimedSpeakerChange = (newSpeakerId) => {
    setClaimedSpeaker(newSpeakerId);
    if (wsRef.current && wsRef.current.isOpen()) {
      wsRef.current.sendControl({
        type: 'SET_CLAIMED_SPEAKER',
        claimed_speaker_id: newSpeakerId
      });
    }
  };

  // Cleanup all hardware and sockets on unmount
  useEffect(() => {
    return () => {
      stopMicrophoneStream();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Real Microphone Duration Timer
  useEffect(() => {
    if (streamStatus === 'LISTENING' || streamStatus === 'ANALYZING') {
      timerRef.current = setInterval(() => {
        setLiveSession((prev) => ({
          ...prev,
          duration: prev.duration + 1
        }));
      }, 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [streamStatus]);

  // Convert Float32Array to 16-bit PCM ArrayBuffer
  const floatTo16BitPCM = (inputFloat32) => {
    const output = new Int16Array(inputFloat32.length);
    for (let i = 0; i < inputFloat32.length; i++) {
      const s = Math.max(-1, Math.min(1, inputFloat32[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return output.buffer;
  };

  const handleLiveAudioAnalysis = (payload) => {
    setStreamStatus('ANALYZING');
    const data = payload.data;
    if (!data) return;

    const isSpeech = !!data.speech_detected;
    const timestampStr = new Date().toTimeString().split(' ')[0];
    const speechStatus = isSpeech ? 'SPEECH DETECTED' : 'SILENCE/AMBIENT';
    const pitchStr = data.prosody?.fundamental_f0_hz ? `${data.prosody.fundamental_f0_hz} Hz` : 'N/A';
    const centroidStr = data.audio?.spectral_centroid_hz ? `${data.audio.spectral_centroid_hz} Hz` : 'N/A';
    const rmsStr = data.audio?.rms !== undefined ? `${data.audio.rms}` : '0.0000';

    setLiveSession((prev) => {
      const newHistItem = {
        timestamp: timestampStr,
        speechDetected: isSpeech,
        rms: data.audio?.rms ?? 0,
        zcr: data.audio?.zcr ?? 0,
        spectralCentroid: data.audio?.spectral_centroid_hz ?? 0,
        spectralFlatness: data.audio?.spectral_flatness ?? 0,
        f0: data.prosody?.fundamental_f0_hz ?? null,
        score: data.fused_trust?.trust_score ?? data.preliminary_trust?.score ?? prev.trust?.trust_score ?? 85,
        riskLevel: data.fused_trust?.risk_level ?? data.preliminary_trust?.risk_level ?? 'SAFE',
        latencyMs: data.latency_ms?.total || 0,
        event: `${speechStatus} | RMS: ${rmsStr} | F0: ${pitchStr} | Centroid: ${centroidStr} | Latency: ${data.latency_ms?.total || 0}ms`
      };

      return {
        ...prev,
        windows: prev.windows + 1,
        speechWindows: prev.speechWindows + (isSpeech ? 1 : 0),
        latestAnalysis: data,
        aasist: data.voice_authenticity?.anti_spoof || prev.aasist,
        ecapa: data.speaker_verification || prev.ecapa,
        prosody: data.prosody || prev.prosody,
        trust: data.fused_trust || data.preliminary_trust || prev.trust,
        history: [newHistItem, ...prev.history.slice(0, 49)]
      };
    });
  };

  const handleLiveWsMessage = (msg) => {
    console.log('[LIVE_EVENT_RECEIVED]', { type: msg.type, call_id: msg.call_id || msg.session_id });
    if (msg.type === 'AUDIO_ANALYSIS' && msg.data) {
      handleLiveAudioAnalysis(msg);
      return;
    }
    if (msg.type === 'AASIST_UPDATE') {
      setLiveSession((prev) => ({ ...prev, aasist: msg.data || prev.aasist }));
      return;
    }
    if (msg.type === 'ECAPA_UPDATE') {
      setLiveSession((prev) => ({ ...prev, ecapa: msg.data || prev.ecapa }));
      return;
    }
    if (msg.type === 'PROSODY_UPDATE') {
      setLiveSession((prev) => ({ ...prev, prosody: msg.data || prev.prosody }));
      return;
    }
    if (msg.type === 'TRANSCRIPT_UPDATE') {
      const payload = msg.data || msg;
      setLiveSession((prev) => ({
        ...prev,
        transcript: {
          text: payload.text || msg.text || '',
          full_text: payload.full_text || msg.full_text || prev.transcript?.full_text || payload.text || '',
          language: payload.language || msg.language || prev.transcript?.language || 'en',
          status: payload.status || msg.status || 'OK',
          engine: payload.engine || msg.engine || 'whisper',
        },
      }));
      return;
    }
    if (msg.type === 'GEMINI_UPDATE') {
      const payload = msg.data || msg;
      setLiveSession((prev) => ({ ...prev, gemini: payload }));
      return;
    }
    if (msg.type === 'CONTEXT_UPDATE') {
      setLiveSession((prev) => ({ ...prev, context: msg.data || prev.context }));
      return;
    }
    if (msg.type === 'TRUST_UPDATE') {
      setLiveSession((prev) => ({ ...prev, trust: msg.data || prev.trust }));
      return;
    }
    if (msg.type === 'INCIDENT_CREATED') {
      setLiveSession((prev) => ({
        ...prev,
        incidents: [msg.data, ...(prev.incidents || [])].filter(Boolean).slice(0, 20),
      }));
      return;
    }
    if (msg.type === 'SESSION_STARTED') {
      setLiveSession((prev) => ({ ...prev, status: 'LIVE', source: 'REAL' }));
      return;
    }
    if (msg.type === 'ERROR') {
      setErrorMessage(msg.data?.message || msg.data?.status || 'Pipeline error');
      return;
    }
    if (msg.type === 'AUDIO_STREAM_STOPPED' || msg.type === 'CALL_FINALIZED' || msg.type === 'SESSION_FINALIZED') {
      const summary = msg.summary || msg.data || {};
      setLiveSession((prev) => {
        const finalized = {
          ...prev,
          active: false,
          endedAt: Date.now(),
          status: 'COMPLETED',
          trust: summary.trust_score != null ? { ...prev.trust, trust_score: summary.trust_score, risk_level: summary.trust_level, recommended_action: summary.action } : prev.trust,
        };
        setCompletedSession(finalized);
        try {
          localStorage.setItem('voxguard:lastRealCall', prev.callId || '');
        } catch {}
        return finalized;
      });
    }
  };

  // Start Real Microphone Capture and Stream PCM16
  const startMicrophoneStream = async () => {
    try {
      setErrorMessage('');
      setStreamStatus('CONNECTING');
      const newCallId = `VS-LIVE-${Date.now()}`;
      setMode('live');
      setChunksSent(0);

      // Clean, fresh live session state
      setCompletedSession(null);
      setLiveSession({
        ...emptyLive,
        active: true,
        callId: newCallId,
        status: 'LIVE',
        startedAt: Date.now(),
      });

      // 1. Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      mediaStreamRef.current = stream;

      const track = stream.getAudioTracks()[0];
      const trackSettings = track ? track.getSettings() : {};
      const trackSampleRate = trackSettings.sampleRate || null;

      // 2. Initialize AudioContext at 16kHz for clean browser-native downsampling
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      let audioCtx;
      try {
        audioCtx = new AudioCtx({ sampleRate: 16000 });
      } catch {
        audioCtx = new AudioCtx();
      }
      audioContextRef.current = audioCtx;
      const actualSampleRate = audioCtx.sampleRate;

      console.log('[AUDIO_HARDWARE_DIAG]', {
        requested_sample_rate: 16000,
        actual_audio_context_sample_rate: actualSampleRate,
        media_stream_track_sample_rate: trackSampleRate,
        channels: 1,
        autoGainControl: true,
      });

      // 3. Clean any existing WebSocket
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      // 4. Connect WebSocket for THIS unique live call session
      const ws = new CallWebSocket(
        newCallId,
        handleLiveWsMessage,
        (err) => {
          console.warn('[LIVE-DATA] WS error:', err);
          if (streamStatus !== 'IDLE') setStreamStatus('ERROR');
        },
        () => {
          // onOpen: Send START_AUDIO_STREAM control frame first
          console.log(`[LIVE-DATA] WebSocket connected for ${newCallId}. Sending START_AUDIO_STREAM.`);
          console.log('[AUDIO_CAPTURE_STARTED]', { sampleRate: actualSampleRate, channels: 1, format: 'pcm_s16le', claimedSpeaker });
          ws.sendControl({
            type: 'START_AUDIO_STREAM',
            sample_rate: actualSampleRate,
            channels: 1,
            format: 'pcm_s16le',
            claimed_speaker_id: claimedSpeaker
          });

          // 5. Connect audio capture graph ONLY AFTER WebSocket is open and START_AUDIO_STREAM is sent
          // This prevents audio chunks arriving before the buffer is initialized on the backend.
          const source = audioCtx.createMediaStreamSource(stream);
          const bufferSize = 4096; // ~85ms chunk at 48kHz
          const processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
          processorRef.current = processor;

          let chunkCount = 0;
          processor.onaudioprocess = (e) => {
            const inputData = e.inputBuffer.getChannelData(0);
            const pcm16Buffer = floatTo16BitPCM(inputData);

            if (wsRef.current && wsRef.current.isOpen()) {
              wsRef.current.sendAudioChunk(pcm16Buffer);
              chunkCount++;
              setChunksSent(chunkCount);
              if (chunkCount === 1 || chunkCount % 20 === 0) {
                console.log('[AUDIO_FRAME_SENT]', { chunkIndex: chunkCount, byteLength: pcm16Buffer.byteLength });
              }
            }
          };

          source.connect(processor);
          processor.connect(audioCtx.destination);
          setStreamStatus('LISTENING');
        }
      );
      wsRef.current = ws;

    } catch (err) {
      console.error('[LIVE-DATA] Microphone stream error:', err);
      setStreamStatus('ERROR');
      if (err.name === 'NotAllowedError') {
        setErrorMessage('Microphone access was denied by browser. Please enable permissions.');
      } else {
        setErrorMessage(err.message || 'Failed to capture microphone stream.');
      }
    }
  };

  // Cleanly Stop Microphone Capture & Release Hardware
  const stopMicrophoneStream = () => {
    setStreamStatus('STOPPING');

    // 1. Stop audio processor
    if (processorRef.current) {
      processorRef.current.onaudioprocess = null;
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    // 2. Close AudioContext
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    // 3. Stop microphone media tracks (releases browser mic indicator)
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // 4. Notify backend & close WebSocket cleanly
    if (wsRef.current) {
      const activeWs = wsRef.current;
      wsRef.current = null;
      if (activeWs.isOpen()) {
        try {
          activeWs.sendControl({ type: 'STOP_AUDIO_STREAM' });
        } catch {}
      }
      setTimeout(() => {
        try {
          activeWs.close();
        } catch {}
      }, 400);
    }

    // 5. Finalize live session state - PRESERVE IT!
    setLiveSession((prev) => ({
      ...prev,
      active: false,
      endedAt: Date.now()
    }));

    setStreamStatus('IDLE');
    // Mode remains 'live' so user sees the real session summary.
  };

  // Demo playback for SIH comparison (Isolated in demo mode)
  const applyStepData = (step) => {
    setDemoCallData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        trust_score: step.trust_score,
        risk_level: step.risk_level,
        duration: step.timestamp,
        voice: { ...prev.voice, ...step.voice },
        speaker: { ...prev.speaker, ...step.speaker },
        prosody: { ...prev.prosody, ...step.prosody },
        conversation: { ...prev.conversation, ...step.conversation },
        transaction: { ...prev.transaction, ...step.transaction },
        transcript_history: [
          ...(prev.transcript_history || []),
          { timestamp: step.timestamp, speaker: 'Caller', text: step.transcript, flagged: step.trust_score < 70 }
        ],
        timeline: [
          ...(prev.timeline || []),
          { time: step.timestamp, score: step.trust_score, label: step.event_label, type: step.trust_score < 30 ? 'critical' : 'info' }
        ]
      };
    });
  };

  const handleSimulateAttack = async () => {
    if (streamStatus === 'LISTENING' || streamStatus === 'ANALYZING') {
      stopMicrophoneStream();
    }
    setMode('demo');
    setIsSimulating(true);

    // Baseline demo call object
    setDemoCallData({
      call_id: 'VS-2026-00081',
      status: 'SIMULATION RUNNING',
      caller: '+1 (415) 890-4412 // UNKNOWN VOIP TRUNK',
      claimed_identity: 'Arun Sharma (CFO)',
      trust_score: 82,
      risk_level: 'SAFE',
      duration: '00:00',
      voice: { ai_probability: 10, spectral_anomaly: 12, harmonic_consistency: 88, voice_naturalness: 92, confidence: 90 },
      speaker: { speaker_similarity: 94.2 },
      prosody: { behavior_anomaly: 15 },
      conversation: { intent: 'Initializing Telephony Ingress...', social_engineering_risk: 10 },
      transaction: { formatted_amount: '₹25,00,000', transaction_risk: 15 },
      transcript_history: [],
      timeline: []
    });

    try {
      const scenario = await api.getScenarioById('clone');
      const steps = scenario.steps || [];
      for (let i = 0; i < steps.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        applyStepData(steps[i]);
      }
    } catch (e) {
      console.warn("Using local step playback");
    } finally {
      setIsSimulating(false);
    }
  };

  const formatDuration = (sec) => {
    const m = String(Math.floor(sec / 60)).padStart(2, '0');
    const s = String(sec % 60).padStart(2, '0');
    return `${m}:${s}`;
  };

  // Helper flags
  const isLiveActive = mode === 'live' && (streamStatus === 'LISTENING' || streamStatus === 'ANALYZING');
  const isLiveEnded = mode === 'live' && !liveSession.active && liveSession.callId !== null;
  const isDemo = mode === 'demo';

  // Dynamic values resolved by current mode
  const currentCallId = mode === 'live'
    ? (liveSession.callId || 'VS-LIVE-STANDBY')
    : mode === 'demo'
    ? (demoCallData?.call_id || 'VS-2026-00081')
    : 'STANDBY-INGRESS';

  const currentDuration = mode === 'live'
    ? formatDuration(liveSession.duration)
    : mode === 'demo'
    ? (demoCallData?.duration || '00:00')
    : '00:00';

  const currentTrustScore = mode === 'live'
    ? (liveSession.trust?.trust_score ?? liveSession.latestAnalysis?.fused_trust?.trust_score ?? liveSession.latestAnalysis?.preliminary_trust?.score ?? 85)
    : mode === 'demo'
    ? (demoCallData?.trust_score ?? 82)
    : 100;

  const currentRiskLevel = mode === 'live'
    ? (liveSession.trust?.risk_level ?? liveSession.latestAnalysis?.fused_trust?.risk_level ?? liveSession.latestAnalysis?.preliminary_trust?.risk_level ?? 'SAFE')
    : mode === 'demo'
    ? (demoCallData?.risk_level || 'SAFE')
    : 'SAFE';

  const isCritical = currentTrustScore < 30;

  const antiSpoof = liveSession.aasist || liveSession.latestAnalysis?.voice_authenticity?.anti_spoof;
  const speakerVerif = liveSession.ecapa || liveSession.latestAnalysis?.speaker_verification;
  const speakerInfo = liveSession.latestAnalysis?.speaker;
  const voiceCloneParadox = liveSession.latestAnalysis?.voice_clone_paradox;

  const currentAiProb = mode === 'live'
    ? (liveSession.latestAnalysis?.voice_authenticity?.ai_probability ?? 0)
    : mode === 'demo'
    ? (demoCallData?.voice?.ai_probability ?? 10)
    : 0;

  const currentSpectralAnomaly = mode === 'live'
    ? (liveSession.latestAnalysis?.voice_authenticity?.spectral_anomaly ?? 0)
    : mode === 'demo'
    ? (demoCallData?.voice?.spectral_anomaly ?? 12)
    : 0;

  const currentHarmonic = mode === 'live'
    ? (liveSession.latestAnalysis?.voice_authenticity?.harmonic_consistency ?? 95)
    : mode === 'demo'
    ? (demoCallData?.voice?.harmonic_consistency ?? 88)
    : 95;

  const currentNaturalness = mode === 'live'
    ? (liveSession.latestAnalysis?.voice_authenticity?.voice_naturalness ?? 95)
    : mode === 'demo'
    ? (demoCallData?.voice?.voice_naturalness ?? 92)
    : 95;

  const currentConfidence = mode === 'live'
    ? (liveSession.latestAnalysis?.voice_authenticity?.confidence ?? 90)
    : mode === 'demo'
    ? (demoCallData?.voice?.confidence ?? 90)
    : 90;

  return (
    <div className="p-6 space-y-6">
      {/* Active Call Ingress Banner */}
      <div className="rounded-xl bg-surface-container-low/85 backdrop-blur-md border border-outline-variant p-5 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary-container via-error to-primary-container"></div>

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl bg-surface-container-high border ${
              isLiveActive
                ? 'border-emerald-400 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.35)]'
                : isLiveEnded
                ? 'border-emerald-500/50 text-emerald-400'
                : isDemo
                ? 'border-primary-container/40 text-primary-container'
                : 'border-outline text-outline'
            } flex items-center justify-center relative`}>
              <span className={`material-symbols-outlined text-2xl ${isLiveActive ? 'animate-pulse' : ''}`}>
                {mode === 'live' ? (isLiveActive ? 'mic' : 'mic_off') : isDemo ? 'play_circle' : 'sensors'}
              </span>
              {isLiveActive && (
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full animate-ping"></span>
              )}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-headline-sm font-bold text-on-surface font-mono">
                  {currentCallId}
                </span>

                {/* Status Badge */}
                <span className={`px-2 py-0.5 rounded font-mono text-xs font-bold ${
                  isLiveActive
                    ? 'bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 animate-pulse'
                    : isLiveEnded
                    ? 'bg-emerald-950/40 border border-emerald-500/40 text-emerald-400'
                    : isDemo
                    ? (isSimulating ? 'bg-amber-950/80 border border-amber-500 text-amber-300 animate-pulse' : 'bg-surface-container border border-outline text-outline')
                    : 'bg-surface-container border border-outline text-outline'
                }`}>
                  {isLiveActive
                    ? `LIVE MIC: ${streamStatus}`
                    : isLiveEnded
                    ? 'LIVE SESSION COMPLETE'
                    : isDemo
                    ? (isSimulating ? 'DEMO ATTACK SIMULATION RUNNING' : 'DEMO ATTACK SIMULATION')
                    : 'INGRESS STANDBY'
                  }
                </span>

                {/* Source Indicator */}
                <span className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold ${
                  mode === 'live'
                    ? 'bg-emerald-900/60 border border-emerald-400/60 text-emerald-200'
                    : isDemo
                    ? 'bg-purple-900/60 border border-purple-400/60 text-purple-200'
                    : 'bg-surface-container-high border border-outline/30 text-outline'
                }`}>
                  {mode === 'live' ? 'SOURCE: REAL WEBSOCKET TELEMETRY' : isDemo ? 'SOURCE: DEMO SIMULATION' : 'SOURCE: IDLE BASELINE'}
                </span>

                {isLiveActive && liveSession.latestAnalysis?.speech_detected && (
                  <span className="px-2 py-0.5 rounded bg-primary-container/20 border border-primary-container/50 text-primary-container font-mono text-xs font-bold">
                    VOICE DETECTED
                  </span>
                )}
              </div>
              <p className="text-xs font-mono text-outline mt-0.5">
                Mode: {mode === 'live'
                  ? `Direct Browser Microphone // PCM16 16kHz Rolling Window (${chunksSent} chunks sent)`
                  : isDemo
                  ? 'Simulated SIH Adversary Telephony Stream (21s Attack Scenario)'
                  : 'Ready for Real Hardware Microphone Capture or Demo Simulation'
                } &bull; Duration: {currentDuration}
              </p>
              {errorMessage && (
                <p className="text-xs font-mono text-error mt-1 flex items-center gap-1">
                  <span className="material-symbols-outlined text-xs">error</span>
                  <span>{errorMessage}</span>
                </p>
              )}
            </div>
          </div>

          {/* Action Buttons: Live Mic Toggle, Demo Simulation, Enforce Action */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Primary Real-Time Microphone Button */}
            {!isLiveActive ? (
              <button
                onClick={startMicrophoneStream}
                disabled={streamStatus === 'CONNECTING'}
                className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.4)] transition-all active:scale-95"
              >
                <span className="material-symbols-outlined text-base">mic</span>
                <span>{streamStatus === 'CONNECTING' ? 'CONNECTING MIC...' : (isLiveEnded ? 'START NEW LIVE SESSION' : 'START LIVE MICROPHONE')}</span>
              </button>
            ) : (
              <button
                onClick={stopMicrophoneStream}
                className="px-5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-mono text-xs font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(239,68,68,0.4)] transition-all active:scale-95 animate-pulse"
              >
                <span className="material-symbols-outlined text-base">mic_off</span>
                <span>STOP LIVE MICROPHONE</span>
              </button>
            )}

            {/* SIH Attack Simulation Demonstration Button */}
            <button
              onClick={handleSimulateAttack}
              disabled={isSimulating || isLiveActive}
              className="px-3.5 py-2 rounded-lg bg-surface-container border border-primary-container/40 hover:border-primary-container text-primary-container font-mono text-xs font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(0,229,255,0.15)] active:scale-95 disabled:opacity-40"
              title="Runs canned 21s attack demonstration scenario for comparison"
            >
              <span className="material-symbols-outlined text-base">play_circle</span>
              <span>{isSimulating ? 'DEMO STREAMING...' : '[DEMO] RUN ATTACK SIMULATION'}</span>
            </button>

            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 rounded-lg bg-error-container hover:bg-error/30 text-on-error-container border border-error/80 font-mono text-xs font-bold tracking-wider flex items-center gap-2 shadow-[0_0_16px_rgba(239,68,68,0.35)] transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-base">block</span>
              <span>ENFORCE ACTION</span>
            </button>
          </div>
        </div>
      </div>

      {/* Real Session Complete Summary Banner (Only shown when live microphone session finishes) */}
      {isLiveEnded && (
        <div className="rounded-xl bg-surface-container border border-emerald-500/40 p-5 shadow-xl space-y-3 font-mono">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-outline-variant/60">
            <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
              <span className="material-symbols-outlined text-lg">check_circle</span>
              <span>LIVE MICROPHONE SESSION SUMMARY (SAVED TO SQLITE)</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-outline">{liveSession.callId}</span>
              <Link
                to={`/investigation/${liveSession.callId}`}
                className="px-3 py-1 rounded bg-primary-container text-on-primary-fixed hover:bg-primary font-mono text-xs font-bold flex items-center gap-1 shadow-[0_0_10px_rgba(0,229,255,0.3)] transition-all"
              >
                <span>OPEN FORENSIC DOSSIER</span>
                <span className="material-symbols-outlined text-xs">arrow_forward</span>
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
            <div className="p-3 rounded bg-surface-container-low border border-outline-variant/30">
              <span className="text-outline text-[10px] block">TOTAL DURATION</span>
              <span className="text-sm font-bold text-on-surface">{formatDuration(liveSession.duration)}</span>
            </div>
            <div className="p-3 rounded bg-surface-container-low border border-outline-variant/30">
              <span className="text-outline text-[10px] block">ANALYSIS WINDOWS</span>
              <span className="text-sm font-bold text-primary-container">{liveSession.windows} windows</span>
            </div>
            <div className="p-3 rounded bg-surface-container-low border border-outline-variant/30">
              <span className="text-outline text-[10px] block">SPEECH DETECTED</span>
              <span className="text-sm font-bold text-emerald-400">{liveSession.speechWindows} windows</span>
            </div>
            <div className="p-3 rounded bg-surface-container-low border border-outline-variant/30">
              <span className="text-outline text-[10px] block">LAST RMS / PITCH</span>
              <span className="text-sm font-bold text-on-surface">
                {liveSession.latestAnalysis?.audio?.rms ?? '0.0000'} / {liveSession.latestAnalysis?.prosody?.fundamental_f0_hz ? `${liveSession.latestAnalysis.prosody.fundamental_f0_hz}Hz` : 'Unvoiced'}
              </span>
            </div>
            <div className="p-3 rounded bg-surface-container-low border border-outline-variant/30">
              <span className="text-outline text-[10px] block">AASIST ANTI-SPOOF</span>
              <span className={`text-sm font-bold ${
                antiSpoof?.prediction === 'SPOOF' ? 'text-error' : antiSpoof?.prediction === 'LIKELY_GENUINE' ? 'text-emerald-400' : 'text-primary-container'
              }`}>
                {antiSpoof?.prediction ? `${antiSpoof.prediction} (${Math.round((antiSpoof.spoof_probability ?? 0) * 100)}% Spoof)` : (isLiveEnded ? 'Evaluated' : 'Pending')}
              </span>
            </div>
            <div className="p-3 rounded bg-surface-container-low border border-outline-variant/30">
              <span className="text-outline text-[10px] block">ECAPA-TDNN SPEAKER</span>
              <span className={`text-sm font-bold ${
                speakerVerif?.status === 'MATCH' ? 'text-emerald-400' : speakerVerif?.status === 'MISMATCH' ? 'text-error' : 'text-primary-container'
              }`}>
                {speakerVerif?.status ? `${speakerVerif.status} (${speakerVerif.similarity_pct ?? 0}%)` : (isLiveEnded ? 'Evaluated' : 'Pending')}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Voice Clone Paradox Alert Banner (Critical Divergence: High Speaker Match + Synthetic Audio) */}
      {((mode === 'live' && voiceCloneParadox?.detected) || (isDemo && (demoCallData?.voice?.ai_probability ?? 0) > 70 && (demoCallData?.speaker?.speaker_similarity ?? 0) > 80)) && (
        <div className="rounded-xl bg-error-container/30 border-2 border-error p-4 shadow-2xl animate-pulse flex items-start gap-3.5">
          <span className="material-symbols-outlined text-error text-3xl shrink-0">warning</span>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold text-error tracking-wide">
                CRITICAL SECURITY ALERT: VOICE CLONE PARADOX DETECTED
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-error text-white uppercase">
                Autonomous Defense Priority
              </span>
            </div>
            <p className="text-xs font-mono text-on-surface leading-relaxed">
              Speaker identity <strong>MATCHES</strong> claimed executive biometrics ({mode === 'live' ? speakerVerif?.similarity_pct : 94.2}%), but acoustic neural analysis confirms <strong>SYNTHETIC / SPOOFED AUDIO</strong> ({mode === 'live' ? Math.round((antiSpoof?.spoof_probability ?? 0) * 100) : 87}% AI probability).
              This divergence confirms weaponized AI voice cloning impersonation!
            </p>
          </div>
        </div>
      )}

      {/* Main 12-Column SOC Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left Column (4 Cols): Trust Score & Multi-Signal Breakdown */}
        <div className="xl:col-span-4 space-y-6">
          {/* Trust Score Arc Card */}
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl text-center">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60 text-xs font-mono text-outline">
              <span>{mode === 'live' ? 'PRELIMINARY TRUST SCORE' : 'DYNAMIC TRUST ENGINE'}</span>
              <span className={mode === 'live' ? 'text-emerald-400 font-bold' : 'text-primary-container'}>
                {mode === 'live' ? 'ACOUSTIC ATTESTATION (PHASE 1)' : isDemo ? 'CONTINUOUS ATTESTATION (SIMULATED)' : 'IDLE MONITOR'}
              </span>
            </div>

            <TrustScoreGauge score={currentTrustScore} riskLevel={currentRiskLevel} isCritical={isCritical} />

            <div className="mt-2 text-xs font-mono text-on-surface-variant px-4 py-2 rounded bg-surface-container-lowest/80 border border-outline-variant/40">
              {mode === 'live'
                ? (liveSession.latestAnalysis?.preliminary_trust?.label || 'Preliminary Trust: 60% Voice Authenticity + 40% Prosody')
                : isDemo
                ? 'Scoring Formula: 30% Voice + 18% Speaker + 10% Prosody + 20% Conversation + 7% Caller + 15% Tx'
                : 'Standby: Ingress capture inactive. Click Start Live Microphone to begin.'
              }
            </div>
          </div>

          {/* Risk Breakdown Card */}
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <h3 className="text-body-md font-bold text-on-surface font-mono uppercase">
                {mode === 'live' ? 'Active Acoustic Telemetry Signals' : 'Risk Vector Contributions'}
              </h3>
              <span className="material-symbols-outlined text-outline text-lg">stacked_bar_chart</span>
            </div>
            <div className="mt-4">
              {mode === 'live' ? (
                <div className="space-y-3 text-xs font-mono">
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">DSP VAD Speech Probability:</span>
                    <span className="font-bold text-primary-container">
                      {liveSession.latestAnalysis?.vad ? `${Math.round(liveSession.latestAnalysis.vad.speech_probability * 100)}%` : (isLiveEnded ? 'Concluded' : 'Listening...')}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">Microphone RMS Energy:</span>
                    <span className="font-bold text-on-surface">
                      {liveSession.latestAnalysis?.audio?.rms ?? '0.0000'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">Spectral Flatness (Wiener):</span>
                    <span className="font-bold text-on-surface">
                      {liveSession.latestAnalysis?.audio?.spectral_flatness ?? '0.0000'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">Spectral Centroid:</span>
                    <span className="font-bold text-on-surface">
                      {liveSession.latestAnalysis?.audio?.spectral_centroid_hz ? `${liveSession.latestAnalysis.audio.spectral_centroid_hz} Hz` : '0.0 Hz'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">Prosodic F0 Pitch:</span>
                    <span className="font-bold text-amber-300">
                      {liveSession.latestAnalysis?.prosody?.fundamental_f0_hz ? `${liveSession.latestAnalysis.prosody.fundamental_f0_hz} Hz` : 'Unvoiced / Ambient'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">Voice Anti-Spoofing (AASIST):</span>
                    <span className={`font-bold text-[11px] ${
                      antiSpoof?.prediction === 'SPOOF'
                        ? 'text-error animate-pulse'
                        : antiSpoof?.prediction === 'LIKELY_GENUINE'
                        ? 'text-emerald-400'
                        : 'text-outline'
                    }`}>
                      {antiSpoof?.status === 'OK'
                        ? `${antiSpoof.prediction} (${(antiSpoof.spoof_probability * 100).toFixed(1)}% Spoof)`
                        : antiSpoof?.status === 'NOT_ENOUGH_AUDIO'
                        ? 'Buffering Audio (4.0s required)'
                        : antiSpoof?.status === 'NO_SPEECH'
                        ? 'No Speech (Ambient)'
                        : isLiveEnded
                        ? 'Concluded'
                        : 'Awaiting Speech'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">Speaker Biometrics (ECAPA):</span>
                    <span className={`font-bold text-[11px] ${
                      speakerVerif?.status === 'MATCH'
                        ? 'text-emerald-400'
                        : speakerVerif?.status === 'MISMATCH'
                        ? 'text-error'
                        : speakerVerif?.status === 'NOT_ENROLLED'
                        ? 'text-purple-300'
                        : 'text-outline'
                    }`}>
                      {speakerVerif?.status
                        ? `${speakerVerif.status} (${speakerVerif.similarity_pct ?? 0}% match)`
                        : isLiveEnded
                        ? 'Concluded'
                        : 'Awaiting Speech'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 flex justify-between items-center">
                    <span className="text-outline">Semantic Analysis:</span>
                    <span className="font-bold text-primary-container text-[11px]">
                      {liveSession.gemini
                        ? `${liveSession.gemini.intent || 'analyzed'} (${liveSession.gemini.risk_score ?? liveSession.gemini.social_engineering_risk ?? 0})`
                        : liveSession.transcript?.status === 'WHISPER_UNAVAILABLE'
                        ? 'WHISPER_UNAVAILABLE'
                        : 'Awaiting transcript'}
                    </span>
                  </div>
                </div>
              ) : (
                <RiskBreakdown
                  breakdown={{
                    voice_synthetic_risk: isDemo ? (demoCallData?.voice?.ai_probability ?? 87) : 0,
                    speaker_anomaly: isDemo ? 85 : 0,
                    conversation_risk: isDemo ? (demoCallData?.conversation?.social_engineering_risk ?? 91) : 0,
                    transaction_risk: isDemo ? (demoCallData?.transaction?.transaction_risk ?? 95) : 0,
                    prosody_anomaly: isDemo ? (demoCallData?.prosody?.behavior_anomaly ?? 72) : 0,
                    caller_risk: isDemo ? 85 : 0,
                  }}
                />
              )}
            </div>
          </div>
        </div>

        {/* Center/Right Column (8 Cols): Diagnostics Bento Grid */}
        <div className="xl:col-span-8 space-y-6">
          {/* Row 1: Voice Authenticity & Speaker Verification */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Voice Authenticity Card */}
            <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary-container text-lg">graphic_eq</span>
                  <h3 className="text-body-md font-bold text-on-surface font-mono">Voice Authenticity</h3>
                </div>
                {mode === 'live' ? (
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                    antiSpoof?.prediction === 'SPOOF'
                      ? 'bg-error-container/40 text-error border-error/50 animate-pulse'
                      : antiSpoof?.prediction === 'LIKELY_GENUINE'
                      ? 'bg-emerald-950 text-emerald-400 border-emerald-500/40'
                      : 'bg-surface-container text-outline border-outline/30'
                  }`}>
                    {antiSpoof?.status === 'OK'
                      ? `${antiSpoof.prediction} (${(antiSpoof.spoof_probability * 100).toFixed(1)}% SPOOF)`
                      : antiSpoof?.status === 'NOT_ENOUGH_AUDIO'
                      ? 'BUFFERING AUDIO (4.0s required)'
                      : antiSpoof?.status === 'NO_SPEECH'
                      ? 'NO SPEECH (AMBIENT)'
                      : 'AASIST ONLINE'}
                  </span>
                ) : isDemo ? (
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${currentAiProb > 60 ? 'bg-error-container/40 text-error border border-error/50' : 'bg-emerald-950 text-emerald-400'}`}>
                    {currentAiProb}% AI PROBABILITY
                  </span>
                ) : (
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-surface-container text-outline border border-outline/30">
                    IDLE
                  </span>
                )}
              </div>

              {/* Live Canvas Spectrogram */}
              <SpectrogramView
                isLive={isLiveActive}
                intensity={mode === 'live'
                  ? (liveSession.latestAnalysis?.audio?.rms ? Math.min(100, Math.round(liveSession.latestAnalysis.audio.rms * 500)) : 15)
                  : isDemo
                  ? (currentAiProb > 30 ? currentAiProb : 25)
                  : 10
                }
              />

              <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">AASIST PREDICTION</span>
                  <span className={`font-bold ${
                    antiSpoof?.prediction === 'SPOOF' ? 'text-error' : antiSpoof?.prediction === 'LIKELY_GENUINE' ? 'text-emerald-400' : 'text-on-surface'
                  }`}>
                    {mode === 'live' ? (antiSpoof?.prediction || (isLiveEnded ? 'CONCLUDED' : 'WAITING SPEECH')) : isDemo ? 'SIMULATED SPOOF' : 'STANDBY'}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">SPOOF PROBABILITY</span>
                  <span className="font-bold text-on-surface">
                    {mode === 'live'
                      ? (antiSpoof?.spoof_probability !== null && antiSpoof?.spoof_probability !== undefined
                          ? `${(antiSpoof.spoof_probability * 100).toFixed(1)}%`
                          : 'Awaiting Speech')
                      : isDemo
                      ? `${demoCallData?.voice?.ai_probability ?? 87}%`
                      : '0%'}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">AASIST LATENCY</span>
                  <span className="font-bold text-emerald-400">
                    {mode === 'live' ? `${antiSpoof?.inference_ms ?? 0} ms` : isDemo ? '14 ms' : '0 ms'}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">MODEL / DEVICE</span>
                  <span className="font-bold text-primary-container">
                    {mode === 'live' ? `${antiSpoof?.model || 'AASIST'} // ${antiSpoof?.device || 'cpu'}` : isDemo ? 'AASIST-Simulated' : 'Standby'}
                  </span>
                </div>
              </div>
            </div>

            {/* Speaker Verification / Biometric Identity Card (Phase 3 ECAPA-TDNN) */}
            <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary text-lg">record_voice_over</span>
                  <h3 className="text-body-md font-bold text-on-surface font-mono">Speaker Identity (ECAPA-TDNN)</h3>
                </div>
                {mode === 'live' ? (
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                    speakerVerif?.status === 'MATCH'
                      ? 'bg-emerald-950/90 text-emerald-400 border-emerald-500/60 shadow-[0_0_8px_rgba(16,185,129,0.3)]'
                      : speakerVerif?.status === 'MISMATCH'
                      ? 'bg-error-container/40 text-error border-error/50 animate-pulse'
                      : speakerVerif?.status === 'NOT_ENROLLED'
                      ? 'bg-purple-950/80 text-purple-300 border-purple-500/40'
                      : speakerVerif?.status === 'NO_SPEECH'
                      ? 'bg-surface-container text-outline border-outline/30'
                      : 'bg-surface-container text-amber-300 border-amber-500/40'
                  }`}>
                    {speakerVerif?.status === 'MATCH'
                      ? `✓ MATCH (${speakerVerif.similarity_pct}%)`
                      : speakerVerif?.status === 'MISMATCH'
                      ? `⚠ MISMATCH (${speakerVerif.similarity_pct}%)`
                      : speakerVerif?.status === 'NOT_ENROLLED'
                      ? 'NOT ENROLLED'
                      : speakerVerif?.status === 'NO_SPEECH'
                      ? 'NO SPEECH (AMBIENT)'
                      : isLiveActive
                      ? 'ANALYZING VOICEPRINT...'
                      : 'ECAPA ONLINE'}
                  </span>
                ) : isDemo ? (
                  <span className="text-xs font-mono text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/40">
                    {demoCallData?.speaker?.speaker_similarity ?? 94.2}% SIMILARITY
                  </span>
                ) : (
                  <span className="text-xs font-mono text-outline font-bold px-2 py-0.5 rounded bg-surface-container border border-outline/40">
                    IDLE
                  </span>
                )}
              </div>

              {/* Claimed Speaker Selector & Ingress Metadata */}
              <div className="p-3.5 rounded-lg bg-surface-container space-y-2.5 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-outline">Claimed Identity:</span>
                  {mode === 'live' ? (
                    <select
                      value={claimedSpeaker}
                      onChange={(e) => handleClaimedSpeakerChange(e.target.value)}
                      className="bg-surface-container-high border border-outline-variant text-on-surface font-mono text-xs rounded px-2 py-0.5 focus:border-primary-container focus:outline-none cursor-pointer max-w-[240px]"
                    >
                      {enrolledSpeakersList.map((s) => (
                        <option key={s.speaker_id} value={s.speaker_id}>
                          {s.display_name} {s.is_synthetic ? '[DEMO SYNTHETIC]' : '✓ [ENROLLED]'}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="font-bold text-on-surface">{isDemo ? (demoCallData?.claimed_identity || 'Arun Sharma (CFO)') : 'Ingress Standby'}</span>
                  )}
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-outline">Enrolled Reference:</span>
                  <span className="text-primary-container font-bold">
                    {mode === 'live'
                      ? (enrolledSpeakersList.find(s => s.speaker_id === claimedSpeaker)?.role || 'Enrolled Executive')
                      : 'FIPS 140-3 #08-X99 (CFO Centroid)'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-outline">Biometric Engine:</span>
                  <span className="text-on-surface">SpeechBrain ECAPA-TDNN (192-dim)</span>
                </div>

                {/* Similarity Progress Bar */}
                <div className="pt-1 space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-outline">Cosine Similarity:</span>
                    <span className="font-bold text-on-surface">
                      {mode === 'live'
                        ? (speakerVerif?.similarity_pct !== undefined ? `${speakerVerif.similarity_pct}%` : 'Awaiting Speech')
                        : isDemo
                        ? `${demoCallData?.speaker?.speaker_similarity ?? 94.2}%`
                        : '0.0%'}
                    </span>
                  </div>
                  <div className="w-full bg-surface-container-highest rounded-full h-2 overflow-hidden relative">
                    <div
                      className={`h-full transition-all duration-300 ${
                        mode === 'live'
                          ? (speakerVerif?.status === 'MATCH' ? 'bg-emerald-500' : speakerVerif?.status === 'MISMATCH' ? 'bg-error' : 'bg-primary-container')
                          : 'bg-emerald-500'
                      }`}
                      style={{
                        width: `${Math.min(100, mode === 'live' ? (speakerVerif?.similarity_pct ?? 0) : (demoCallData?.speaker?.speaker_similarity ?? 94.2))}%`
                      }}
                    />
                    {/* Threshold marker at 80% */}
                    <div className="absolute top-0 bottom-0 w-0.5 bg-white/70" style={{ left: '80%' }} title="Threshold: 80%" />
                  </div>
                  <div className="flex justify-between text-[9px] text-outline pt-0.5">
                    <span>0% (Impostor)</span>
                    <span className="text-amber-300 font-bold">▲ Match Threshold: 80%</span>
                    <span>100% (Identical)</span>
                  </div>
                </div>
              </div>

              {/* Forensic Diagnostic Tiles */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">BIOMETRIC STATUS</span>
                  <span className={`font-bold ${
                    speakerVerif?.status === 'MATCH' ? 'text-emerald-400' : speakerVerif?.status === 'MISMATCH' ? 'text-error' : speakerVerif?.status === 'INCONCLUSIVE' ? 'text-blue-400' : 'text-on-surface'
                  }`}>
                    {mode === 'live'
                      ? (speakerVerif?.status === 'INCONCLUSIVE' && (speakerVerif?.speech_windows_accumulated ?? 0) > 0
                          ? `INCONCLUSIVE (${speakerVerif.speech_windows_accumulated}/${speakerVerif.min_speaker_windows ?? 3})`
                          : (speakerVerif?.status || (isLiveEnded ? 'CONCLUDED' : 'WAITING SPEECH')))
                      : isDemo ? 'MATCH' : 'STANDBY'}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">SPEECH ACCUMULATION</span>
                  <span className="font-bold text-primary-container">
                    {mode === 'live' ? `${speakerVerif?.speech_windows_accumulated ?? 0} windows` : isDemo ? 'Continuous' : '0 windows'}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">ECAPA LATENCY</span>
                  <span className="font-bold text-emerald-400">
                    {mode === 'live' ? `${speakerVerif?.inference_ms ?? 0} ms` : isDemo ? '18 ms' : '0 ms'}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">EMBEDDING DIM</span>
                  <span className="font-bold text-on-surface">192-dim normalized</span>
                </div>
              </div>

              {/* Security Alert / Status Box */}
              {mode === 'live' ? (
                voiceCloneParadox?.detected ? (
                  <div className="p-3 rounded-lg bg-error-container/30 border border-error/80 text-xs font-mono text-error">
                    <div className="font-bold flex items-center gap-1.5 mb-1">
                      <span className="material-symbols-outlined text-sm">warning</span>
                      <span>VOICE CLONE PARADOX DETECTED</span>
                    </div>
                    <p className="text-[11px] text-on-surface/90 leading-relaxed">
                      Speaker identity matches <strong>{speakerVerif?.display_name}</strong> ({speakerVerif?.similarity_pct}%), but audio exhibits synthetic vocoder artifacts ({Math.round((antiSpoof?.spoof_probability ?? 0) * 100)}% spoof). This confirms an AI cloned impersonation attack!
                    </p>
                  </div>
                ) : speakerVerif?.status === 'MATCH' ? (
                  <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/50 text-xs font-mono text-emerald-300">
                    <div className="font-bold flex items-center gap-1.5 mb-1">
                      <span className="material-symbols-outlined text-sm">verified_user</span>
                      <span>BIOMETRIC IDENTITY VERIFIED</span>
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      Ingress voice matches enrolled profile <strong>{speakerVerif?.display_name}</strong> with {speakerVerif?.similarity_pct}% similarity (Threshold: 80%).
                    </p>
                  </div>
                ) : speakerVerif?.status === 'MISMATCH' ? (
                  <div className="p-3 rounded-lg bg-amber-950/60 border border-amber-500/50 text-xs font-mono text-amber-300">
                    <div className="font-bold flex items-center gap-1.5 mb-1">
                      <span className="material-symbols-outlined text-sm">error</span>
                      <span>BIOMETRIC IDENTITY MISMATCH</span>
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      Voiceprint similarity ({speakerVerif?.similarity_pct}%) falls below threshold for claimed identity <strong>{speakerVerif?.display_name}</strong>.
                    </p>
                  </div>
                ) : speakerVerif?.status === 'INCONCLUSIVE' && (speakerVerif?.speech_windows_accumulated ?? 0) > 0 ? (
                  <div className="p-3 rounded-lg bg-blue-950/60 border border-blue-500/50 text-xs font-mono text-blue-300">
                    <div className="font-bold flex items-center gap-1.5 mb-1">
                      <span className="material-symbols-outlined text-sm">sync</span>
                      <span>ACCUMULATING VOICEPRINT ({speakerVerif.speech_windows_accumulated}/{speakerVerif.min_speaker_windows ?? 3} WINDOWS)</span>
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      Evaluating rolling speech centroid against claimed identity <strong>{speakerVerif?.display_name}</strong>. Current similarity: {speakerVerif?.similarity_pct}% (Threshold: {Math.round((speakerVerif?.threshold ?? 0.8) * 100)}%). Multi-window attestation activates after {speakerVerif?.min_speaker_windows ?? 3} valid speech windows.
                    </p>
                  </div>
                ) : (
                  <div className="p-3 rounded-lg bg-surface-container-highest/60 border border-outline-variant/60 text-xs font-mono text-on-surface-variant">
                    <div className="font-bold flex items-center gap-1.5 mb-1 text-primary-container">
                      <span className="material-symbols-outlined text-sm">info</span>
                      <span>{isLiveActive ? 'ECAPA-TDNN LISTENING FOR SPEECH' : 'SESSION COMPLETED'}</span>
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      {isLiveActive
                        ? 'Speak clearly into the microphone. Voice windows are evaluated against the claimed speaker profile in 3-second rolling increments.'
                        : `Microphone recording stopped. Session telemetry preserved (${liveSession.windows} windows analyzed).`
                      }
                    </p>
                  </div>
                )
              ) : isDemo ? (
                <div className="p-3 rounded-lg bg-error-container/20 border border-error/50 text-xs font-mono text-error">
                  <div className="font-bold flex items-center gap-1.5 mb-1">
                    <span className="material-symbols-outlined text-sm">warning</span>
                    <span>SECURITY PARADOX DETECTED (SIMULATED)</span>
                  </div>
                  <p className="text-[11px] text-on-surface/90 leading-relaxed">
                    Speaker similarity is <strong>HIGH (94.2%)</strong> while Voice Authenticity is <strong>LOW (87% AI)</strong>. This confirms deliberate deepfake voice impersonation!
                  </p>
                </div>
              ) : (
                <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/40 text-xs font-mono text-outline">
                  Click <strong>START LIVE MICROPHONE</strong> to stream audio from your microphone, or run the demo simulation.
                </div>
              )}
            </div>
          </div>

          {/* Row 2: Live Transcript & Conversation Intelligence */}
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary-fixed-dim text-lg">subtitles</span>
                <h3 className="text-body-md font-bold text-on-surface font-mono">
                  {mode === 'live' ? 'Live Whisper Transcript & Gemini Intelligence' : 'Streaming Transcript & NLP Forensics'}
                </h3>
              </div>
              <span className="text-xs font-mono text-outline">
                {mode === 'live' ? 'faster-whisper ASR + Gemini conversation risk (not anti-spoof)' : 'DEMO / SIMULATED transcript'}
              </span>
            </div>

            {/* Forensic Stream / Transcript Stream container */}
            <div className="space-y-2 max-h-48 overflow-y-auto pr-2">
              {mode === 'live' ? (
                <div className="space-y-3">
                  {liveSession.transcript?.full_text ? (
                    <div className="p-3 rounded-lg bg-surface-container border border-primary-container/60 text-xs font-mono text-on-surface">
                      <div className="flex items-center justify-between text-[10px] text-primary-container font-bold mb-1.5 pb-1 border-b border-outline-variant/30">
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                          LIVE TRANSCRIPT ({liveSession.transcript.engine || 'whisper'})
                        </span>
                        <span className="text-outline uppercase">LANG: {liveSession.transcript.language || 'en'}</span>
                      </div>
                      <div className="whitespace-pre-wrap text-body-sm leading-relaxed text-on-surface font-sans">
                        "{liveSession.transcript.full_text}"
                      </div>
                      {liveSession.transcript.status && liveSession.transcript.status !== 'OK' && (
                        <div className="mt-2 text-amber-300 text-[10px]">{liveSession.transcript.status}</div>
                      )}
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/30 text-xs font-mono text-outline text-center">
                      {isLiveActive
                        ? 'Listening for speech... Whisper will transcribe speech windows incrementally.'
                        : 'No live audio windows captured in this session.'
                      }
                    </div>
                  )}

                  {liveSession.history.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <div className="text-[10px] font-mono text-outline uppercase tracking-wider">Acoustic Window Stream ({liveSession.history.length})</div>
                      {liveSession.history.slice(0, 5).map((logItem, idx) => (
                        <div
                          key={idx}
                          className={`p-2 rounded-lg border text-xs font-mono transition-all ${
                            logItem.speechDetected
                              ? 'bg-surface-container border-primary-container/30 text-on-surface'
                              : 'bg-surface-container-lowest border-outline-variant/20 text-outline'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[10px] text-outline mb-0.5">
                            <span className="font-bold text-primary-container">[{logItem.timestamp}]</span>
                            <span className="font-bold text-emerald-400">Score: {logItem.score}</span>
                          </div>
                          <p className="text-[11px] leading-tight truncate">{logItem.event}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : isDemo ? (
                demoCallData?.transcript_history?.length === 0 ? (
                  <div className="p-4 rounded-lg bg-surface-container border border-outline-variant/30 text-xs font-mono text-outline text-center">
                    Simulation running... Telephony transcript frames incoming.
                  </div>
                ) : (
                  demoCallData?.transcript_history?.map((t, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border text-xs font-mono transition-all ${
                        t.flagged
                          ? 'bg-error-container/25 border-error/50 text-on-surface'
                          : 'bg-surface-container border-outline-variant/40 text-on-surface-variant'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px] text-outline mb-1">
                        <span className="font-bold text-primary-container">[{t.timestamp}] {t.speaker}</span>
                        {t.category && (
                          <span className="px-1.5 py-0.5 rounded bg-error-container text-error font-bold">
                            {t.category}
                          </span>
                        )}
                      </div>
                      <p className="text-body-sm text-on-surface leading-normal">{t.text}</p>
                    </div>
                  ))
                )
              ) : (
                <div className="p-4 rounded-lg bg-surface-container border border-outline-variant/30 text-xs font-mono text-outline text-center">
                  Standby. Microphone audio analysis and forensics telemetry will appear here when active.
                </div>
              )}
            </div>

            {/* Semantic Intent & Transaction Exposure */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-outline-variant/60 text-xs font-mono">
              <div className="p-3 rounded-lg bg-surface-container space-y-1.5">
                <span className="text-outline uppercase text-[10px]">CONVERSATION INTENT:</span>
                <div className={mode === 'live' ? 'text-primary-container font-bold text-sm' : isDemo ? 'text-error font-bold text-sm' : 'text-outline font-bold text-sm'}>
                  {mode === 'live'
                    ? (liveSession.gemini?.intent || (liveSession.transcript?.full_text ? 'Transcript received — awaiting Gemini increment' : 'Awaiting live speech for Whisper ASR'))
                    : isDemo
                    ? (demoCallData?.conversation?.intent || 'Coercive Wire Transfer Hijack')
                    : 'Awaiting Ingress Stream'
                  }
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {mode === 'live' ? (
                    <>
                      {liveSession.gemini?.authority_impersonation && <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Authority</span>}
                      {liveSession.gemini?.financial_request && <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Financial</span>}
                      {liveSession.gemini?.social_engineering && <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Social engineering</span>}
                      {liveSession.gemini?.urgency && <span className="px-1.5 py-0.5 rounded bg-amber-950/40 text-amber-300 text-[10px]">Urgency</span>}
                      {!liveSession.gemini && <span className="px-1.5 py-0.5 rounded bg-surface-container-highest text-outline text-[10px]">REAL microphone — no canned transcript</span>}
                    </>
                  ) : isDemo ? (
                    <>
                      <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Authority Impersonation</span>
                      <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Urgency Induction</span>
                      <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Secrecy Coercion</span>
                    </>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded bg-surface-container-highest text-outline text-[10px]">Standby</span>
                  )}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-surface-container space-y-1.5">
                <span className="text-outline uppercase text-[10px]">EXPOSURE &amp; CONTEXT:</span>
                <div className="flex justify-between">
                  <span className="text-outline">Audio Transport:</span>
                  <span className="font-bold text-on-surface">{mode === 'live' ? 'WebSocket PCM16 Raw (16kHz)' : isDemo ? 'SIP VoIP Ingress' : 'Inactive'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-outline">Analysis Latency:</span>
                  <span className="text-emerald-400 font-bold">
                    {mode === 'live' ? `${liveSession.latestAnalysis?.latency_ms?.total || 0} ms` : isDemo ? '18 ms' : '0 ms'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-outline">Acoustic Status:</span>
                  <span className="font-bold text-primary-container">
                    {mode === 'live'
                      ? (liveSession.latestAnalysis?.speech_detected ? 'Active Speech Detected' : isLiveEnded ? 'Session Concluded' : 'Silence / Floor')
                      : isDemo
                      ? '95% Anomaly'
                      : 'Standby'
                    }
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {mode === 'live' && liveSession.callId && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant space-y-2 font-mono text-xs">
            <div className="font-bold text-primary-container">DEMO_CONTEXT (explicit, not telephony)</div>
            <input className="w-full bg-surface-container border border-outline-variant rounded px-2 py-1" placeholder="Claimed identity" value={demoContextDraft.claimed_identity} onChange={(e) => setDemoContextDraft({ ...demoContextDraft, claimed_identity: e.target.value })} />
            <input className="w-full bg-surface-container border border-outline-variant rounded px-2 py-1" placeholder="Caller number" value={demoContextDraft.caller_number} onChange={(e) => setDemoContextDraft({ ...demoContextDraft, caller_number: e.target.value })} />
            <input className="w-full bg-surface-container border border-outline-variant rounded px-2 py-1" placeholder="Amount" value={demoContextDraft.transaction_amount} onChange={(e) => setDemoContextDraft({ ...demoContextDraft, transaction_amount: e.target.value })} />
            <input className="w-full bg-surface-container border border-outline-variant rounded px-2 py-1" placeholder="Beneficiary" value={demoContextDraft.beneficiary} onChange={(e) => setDemoContextDraft({ ...demoContextDraft, beneficiary: e.target.value })} />
            <button onClick={submitDemoContext} className="px-3 py-1 rounded bg-primary-container text-on-primary-fixed font-bold">Apply labelled context</button>
            <div className="text-outline">{liveSession.context?.label || 'No context supplied'}</div>
          </div>
          <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant space-y-2 font-mono text-xs">
            <div className="font-bold text-primary-container">Gemini reasoning</div>
            <p className="text-on-surface">{liveSession.gemini?.reasoning || liveSession.gemini?.summary || 'No conversation analysis yet.'}</p>
            <div>Recommended (evidence only): {liveSession.gemini?.recommended_action || 'n/a'}</div>
            <div>Trust action: {liveSession.trust?.recommended_action || liveSession.latestAnalysis?.preliminary_trust?.recommended_action || 'MONITOR'}</div>
          </div>
          <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant space-y-2 font-mono text-xs">
            <div className="font-bold text-primary-container">Incidents</div>
            {(liveSession.incidents || []).length === 0 ? (
              <div className="text-outline">No incidents this session.</div>
            ) : liveSession.incidents.map((inc) => (
              <div key={inc.incident_id} className="p-2 rounded border border-error/40 text-error">
                {inc.incident_id}: {inc.title} ({inc.severity})
              </div>
            ))}
            {completedSession?.callId && (
              <Link to={`/investigation/${completedSession.callId}`} className="block text-primary-container font-bold">Open last completed REAL session</Link>
            )}
          </div>
        </div>
      )}

      {/* Action Execution Modal */}
      <ActionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        callId={currentCallId}
        onConfirm={(action, reason) => triggerSecurityAction(currentCallId, action, reason)}
      />
    </div>
  );
}
