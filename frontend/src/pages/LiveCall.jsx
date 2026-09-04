import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import { CallWebSocket } from '../services/websocket';
import TrustScoreGauge from '../components/trust/TrustScoreGauge';
import RiskBreakdown from '../components/trust/RiskBreakdown';
import SpectrogramView from '../components/voice/SpectrogramView';
import ActionModal from '../components/security/ActionModal';

export default function LiveCall() {
  const { activeCallData, activeCallId, triggerSecurityAction } = useApp();
  const [callData, setCallData] = useState(activeCallData || null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simStep, setSimStep] = useState(0);

  // Initialize or fetch call data
  useEffect(() => {
    if (!callData) {
      api.getCallById(activeCallId)
        .then((res) => setCallData(res))
        .catch(() => {});
    }
  }, [activeCallId]);

  // Connect WebSocket
  useEffect(() => {
    const ws = new CallWebSocket(
      activeCallId,
      (msg) => {
        if (msg.type === 'TRUST_UPDATE' && msg.data) {
          applyStepData(msg.data);
        }
      },
      (err) => console.log('WS offline, local simulation ready.')
    );
    return () => ws.close();
  }, [activeCallId]);

  const applyStepData = (step) => {
    setCallData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        trust_score: step.trust_score,
        risk_level: step.risk_level,
        duration: step.timestamp,
        voice: {
          ...prev.voice,
          ...step.voice,
        },
        speaker: {
          ...prev.speaker,
          ...step.speaker,
        },
        prosody: {
          ...prev.prosody,
          ...step.prosody,
        },
        conversation: {
          ...prev.conversation,
          ...step.conversation,
        },
        transaction: {
          ...prev.transaction,
          ...step.transaction,
        },
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
    setIsSimulating(true);
    try {
      const scenario = await api.getScenarioById('clone');
      const steps = scenario.steps || [];

      // Step progressively through the 21s attack timeline
      for (let i = 0; i < steps.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        applyStepData(steps[i]);
        setSimStep(i);
      }
    } catch (e) {
      console.warn("Using local step playback");
    } finally {
      setIsSimulating(false);
    }
  };

  const currentScore = callData?.trust_score ?? 9;
  const isCritical = currentScore < 30;

  return (
    <div className="p-6 space-y-6">
      {/* Active Call Ingress Banner */}
      <div className="rounded-xl bg-surface-container-low/85 backdrop-blur-md border border-outline-variant p-5 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary-container via-error to-primary-container"></div>
        
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-surface-container-high border border-primary-container/40 flex items-center justify-center text-primary-container shadow-[0_0_20px_rgba(0,229,255,0.25)] relative">
              <span className="material-symbols-outlined text-2xl animate-pulse">phone_in_talk</span>
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-error rounded-full animate-ping"></span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-headline-sm font-bold text-on-surface font-mono">
                  {callData?.call_id || 'VS-2026-00081'}
                </span>
                <span className="px-2 py-0.5 rounded bg-error-container/30 border border-error/50 text-error font-mono text-xs font-bold animate-pulse">
                  {callData?.status || 'CRITICAL RISK'}
                </span>
              </div>
              <p className="text-xs font-mono text-outline mt-0.5">
                Ingress: {callData?.caller || 'Unknown VoIP Trunk // Frankfurt Proxy'} &bull; Duration: {callData?.duration || '00:21'}
              </p>
            </div>
          </div>

          {/* Quick Simulation & Action Buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleSimulateAttack}
              disabled={isSimulating}
              className="px-4 py-2 rounded-lg bg-surface-container border border-primary-container/40 hover:border-primary-container text-primary-container font-mono text-xs font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(0,229,255,0.15)] active:scale-95"
            >
              <span className="material-symbols-outlined text-base">play_circle</span>
              <span>{isSimulating ? 'SIMULATION STREAMING...' : 'RUN ATTACK SIMULATION (00:00 → 00:21)'}</span>
            </button>

            <button
              onClick={() => setIsModalOpen(true)}
              className="px-5 py-2 rounded-lg bg-error-container hover:bg-error/30 text-on-error-container border border-error/80 font-mono text-xs font-bold tracking-wider flex items-center gap-2 shadow-[0_0_16px_rgba(239,68,68,0.35)] transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-base">block</span>
              <span>ENFORCE ACTION</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main 12-Column SOC Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left Column (4 Cols): Trust Score & Multi-Signal Breakdown */}
        <div className="xl:col-span-4 space-y-6">
          {/* Trust Score Arc Card */}
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl text-center">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60 text-xs font-mono text-outline">
              <span>DYNAMIC TRUST ENGINE</span>
              <span className="text-primary-container">CONTINUOUS ATTESTATION</span>
            </div>

            <TrustScoreGauge score={currentScore} riskLevel={callData?.risk_level || 'CRITICAL'} isCritical={isCritical} />

            <div className="mt-2 text-xs font-mono text-on-surface-variant px-4 py-2 rounded bg-surface-container-lowest/80 border border-outline-variant/40">
              Scoring Formula: 30% Voice + 18% Speaker + 10% Prosody + 20% Conversation + 7% Caller + 15% Tx
            </div>
          </div>

          {/* Risk Breakdown Card */}
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <h3 className="text-body-md font-bold text-on-surface font-mono uppercase">
                Risk Vector Contributions
              </h3>
              <span className="material-symbols-outlined text-outline text-lg">stacked_bar_chart</span>
            </div>
            <div className="mt-4">
              <RiskBreakdown
                breakdown={{
                  voice_synthetic_risk: callData?.voice?.ai_probability ?? 87,
                  speaker_anomaly: 85,
                  conversation_risk: callData?.conversation?.social_engineering_risk ?? 91,
                  transaction_risk: callData?.transaction?.transaction_risk ?? 95,
                  prosody_anomaly: callData?.prosody?.behavior_anomaly ?? 72,
                  caller_risk: callData?.caller_context?.caller_risk ?? 85,
                }}
              />
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
                <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${callData?.voice?.ai_probability > 60 ? 'bg-error-container/40 text-error border border-error/50' : 'bg-emerald-950 text-emerald-400'}`}>
                  {callData?.voice?.ai_probability ?? 87}% AI PROBABILITY
                </span>
              </div>

              {/* Live Canvas Spectrogram */}
              <SpectrogramView isLive={true} intensity={callData?.voice?.ai_probability ?? 87} />

              <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">SPECTRAL ANOMALY</span>
                  <span className="font-bold text-on-surface">{callData?.voice?.spectral_anomaly ?? 82}%</span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">HARMONIC CONSISTENCY</span>
                  <span className="font-bold text-on-surface">{callData?.voice?.harmonic_consistency ?? 31}%</span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">VOICE NATURALNESS</span>
                  <span className="font-bold text-on-surface">{callData?.voice?.voice_naturalness ?? 24}%</span>
                </div>
                <div className="p-2 rounded bg-surface-container">
                  <span className="text-outline text-[10px] block">CONFIDENCE</span>
                  <span className="font-bold text-primary-container">{callData?.voice?.confidence ?? 91}%</span>
                </div>
              </div>
            </div>

            {/* Speaker Verification Card */}
            <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary text-lg">record_voice_over</span>
                  <h3 className="text-body-md font-bold text-on-surface font-mono">Speaker Identity</h3>
                </div>
                <span className="text-xs font-mono text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/40">
                  {callData?.speaker?.speaker_similarity ?? 94.2}% SIMILARITY
                </span>
              </div>

              <div className="p-3.5 rounded-lg bg-surface-container space-y-2 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-outline">Claimed Executive:</span>
                  <span className="font-bold text-on-surface">Arun Sharma (CFO)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-outline">Biometric Profile:</span>
                  <span className="text-primary-container">FIPS 140-3 #08-X99</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-outline">Identity Confidence:</span>
                  <span className="text-amber-400 font-bold">High Match</span>
                </div>
              </div>

              {/* Critical differentiator alert box */}
              <div className="p-3 rounded-lg bg-error-container/20 border border-error/50 text-xs font-mono text-error">
                <div className="font-bold flex items-center gap-1.5 mb-1">
                  <span className="material-symbols-outlined text-sm">warning</span>
                  <span>SECURITY PARADOX DETECTED</span>
                </div>
                <p className="text-[11px] text-on-surface/90 leading-relaxed">
                  Speaker similarity is <strong>HIGH (94.2%)</strong> while Voice Authenticity is <strong>LOW (87% AI)</strong>. This confirms deliberate deepfake voice impersonation!
                </p>
              </div>
            </div>
          </div>

          {/* Row 2: Live Transcript & Conversation Intelligence */}
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary-fixed-dim text-lg">subtitles</span>
                <h3 className="text-body-md font-bold text-on-surface font-mono">
                  Live Streaming Transcript &amp; NLP Forensics
                </h3>
              </div>
              <span className="text-xs font-mono text-outline">Whisper-v3 + Gemini Semantic Engine</span>
            </div>

            {/* Transcript stream container */}
            <div className="space-y-2 max-h-48 overflow-y-auto pr-2">
              {callData?.transcript_history?.map((t, idx) => (
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
              ))}
            </div>

            {/* Semantic Intent & Transaction Exposure */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-outline-variant/60 text-xs font-mono">
              <div className="p-3 rounded-lg bg-surface-container space-y-1.5">
                <span className="text-outline uppercase text-[10px]">CONVERSATION INTENT:</span>
                <div className="text-error font-bold text-sm">
                  {callData?.conversation?.intent || 'Coercive Wire Transfer Hijack'}
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Authority Impersonation</span>
                  <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Urgency Induction</span>
                  <span className="px-1.5 py-0.5 rounded bg-error-container/30 text-error text-[10px]">Secrecy Coercion</span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-surface-container space-y-1.5">
                <span className="text-outline uppercase text-[10px]">EXPOSURE &amp; CONTEXT:</span>
                <div className="flex justify-between">
                  <span className="text-outline">Requested Amount:</span>
                  <span className="font-bold text-error">₹25,00,000 (INR)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-outline">Beneficiary:</span>
                  <span className="text-amber-400 font-bold">New Unverified Account</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-outline">Transaction Risk:</span>
                  <span className="text-error font-bold">95% Anomaly</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Execution Modal */}
      <ActionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        callId={callData?.call_id || 'VS-2026-00081'}
        onConfirm={(action, reason) => triggerSecurityAction(callData?.call_id || 'VS-2026-00081', action, reason)}
      />
    </div>
  );
}
