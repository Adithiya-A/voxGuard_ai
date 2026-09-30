import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';
import TrustScoreGauge from '../components/trust/TrustScoreGauge';
import SpectrogramView from '../components/voice/SpectrogramView';

export default function DemoSimulator() {
  const navigate = useNavigate();
  const { setActiveCallData, setActiveCallId, addNotification } = useApp();
  const [activeScenarioKey, setActiveScenarioKey] = useState('clone');
  const [scenarioData, setScenarioData] = useState(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1500);

  useEffect(() => {
    loadScenario(activeScenarioKey);
  }, [activeScenarioKey]);

  const loadScenario = async (key) => {
    try {
      const data = await api.getScenarioById(key);
      setScenarioData(data);
      setCurrentStepIndex(0);
      setIsPlaying(false);
    } catch (e) {
      console.warn("Using fallback scenario");
    }
  };

  useEffect(() => {
    let timer;
    if (isPlaying && scenarioData) {
      timer = setTimeout(() => {
        if (currentStepIndex < scenarioData.steps.length - 1) {
          setCurrentStepIndex((prev) => prev + 1);
        } else {
          setIsPlaying(false);
          addNotification({
            type: activeScenarioKey === 'clone' ? 'critical' : 'safe',
            title: activeScenarioKey === 'clone' ? 'SIMULATION: ATTACK MITIGATED' : 'SIMULATION: ATTESTATION COMPLETE',
            message: `Completed automated playback of ${scenarioData.title}`
          });
        }
      }, playbackSpeed);
    }
    return () => clearTimeout(timer);
  }, [isPlaying, currentStepIndex, scenarioData, playbackSpeed]);

  const currentStep = scenarioData?.steps?.[currentStepIndex] || {
    timestamp: '00:00',
    trust_score: 82,
    risk_level: 'WARNING',
    action: 'ALLOW',
    transcript: 'Initiating simulated PBX wiretap...',
    voice: { ai_probability: 15 },
    speaker: { speaker_similarity: 82.0 },
    event_label: 'Call Handshake'
  };

  const handleLaunchToLiveCall = () => {
    // Inject active scenario state into the Live Call page
    setActiveCallId('VS-2026-00081');
    navigate('/live-call');
  };

  const scenarios = [
    { key: 'clone', label: 'Scenario 2: AI Voice Clone (CFO Impersonation)', badge: 'CRITICAL ATTACK', desc: 'Weaponized ElevenLabs synthesis + ₹25L wire hijack. Trust drops 82 → 09.' },
    { key: 'genuine', label: 'Scenario 1: Genuine CFO Call', badge: 'AUTHENTIC BASELINE', desc: 'Legitimate executive voiceprint + clean harmonics. Trust Score: 94.' },
    { key: 'social_eng', label: 'Scenario 3: Social Engineering / SIM-Swap', badge: 'COERCIVE VENDOR', desc: 'Human caller impersonating IT Helpdesk to harvest OTP. Trust Score: 34.' }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-outline-variant/60 pb-5">
        <div>
          <div className="flex items-center gap-2 text-label-code-sm font-mono text-outline mb-1 text-xs">
            <span>DEFENSE LABS</span>
            <span>/</span>
            <span className="text-primary-container">ADVERSARY SIMULATION SANDBOX</span>
          </div>
          <h1 className="text-headline-lg font-bold text-on-surface tracking-tight flex items-center gap-3">
            <span>Red-Team Attack Simulator &amp; SIH Demo Engine</span>
            <span className="px-2.5 py-0.5 rounded bg-error-container/30 border border-error/50 text-error font-mono text-xs font-bold animate-pulse">
              AIR-GAPPED VIRTUAL PBX
            </span>
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1 font-mono text-xs">
            Demonstrate real-time continuous degradation as synthetic acoustic anomalies and coercive intent trigger autonomous mitigation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleLaunchToLiveCall}
            className="px-4 py-2.5 rounded-lg bg-primary-container text-on-primary-fixed hover:bg-primary font-mono text-xs font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(0,229,255,0.3)]"
          >
            <span className="material-symbols-outlined text-base">open_in_new</span>
            <span>TRANSFER TO LIVE CALL SOC VIEW</span>
          </button>
        </div>
      </div>

      {/* Scenario Selector Ribbon */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scenarios.map((sc) => (
          <div
            key={sc.key}
            onClick={() => setActiveScenarioKey(sc.key)}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              activeScenarioKey === sc.key
                ? 'bg-surface-container border-primary-container shadow-[0_0_20px_rgba(0,229,255,0.15)]'
                : 'bg-surface-container-low/75 border-outline-variant hover:border-outline'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-surface-container-highest text-primary-container">
                {sc.badge}
              </span>
              {activeScenarioKey === sc.key && (
                <span className="w-2 h-2 rounded-full bg-primary-container animate-ping"></span>
              )}
            </div>
            <h3 className="text-body-sm font-bold text-on-surface font-mono">{sc.label}</h3>
            <p className="text-xs text-on-surface-variant mt-1 font-mono">{sc.desc}</p>
          </div>
        ))}
      </div>

      {/* Interactive Simulation Dashboard (12 Cols) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left Column: Timeline & Playback Controls (7 Cols) */}
        <div className="xl:col-span-7 space-y-6">
          {/* Controls Bar */}
          <div className="p-5 rounded-xl bg-surface-container-low/85 backdrop-blur-md border border-outline-variant shadow-xl font-mono flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className={`px-4 py-2 rounded-lg font-bold text-xs flex items-center gap-2 transition-all ${
                  isPlaying
                    ? 'bg-amber-500 text-surface-container-lowest shadow-[0_0_12px_rgba(245,158,11,0.4)]'
                    : 'bg-primary-container text-on-primary-fixed shadow-[0_0_12px_rgba(0,229,255,0.3)]'
                }`}
              >
                <span className="material-symbols-outlined text-base">
                  {isPlaying ? 'pause' : 'play_arrow'}
                </span>
                <span>{isPlaying ? 'PAUSE' : 'PLAY SIMULATION'}</span>
              </button>

              <button
                onClick={() => {
                  if (scenarioData && currentStepIndex < scenarioData.steps.length - 1) {
                    setCurrentStepIndex((prev) => prev + 1);
                  }
                }}
                disabled={isPlaying || currentStepIndex >= (scenarioData?.steps?.length || 1) - 1}
                className="px-3 py-2 rounded-lg bg-surface-container border border-outline text-on-surface hover:border-primary-container disabled:opacity-40 text-xs flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-base">skip_next</span>
                <span>Step &rarr;</span>
              </button>

              <button
                onClick={() => {
                  setCurrentStepIndex(0);
                  setIsPlaying(false);
                }}
                className="px-3 py-2 rounded-lg bg-surface-container border border-outline text-outline hover:text-on-surface text-xs"
              >
                Reset
              </button>
            </div>

            {/* Speed Selector */}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-outline">Cadence:</span>
              <button
                onClick={() => setPlaybackSpeed(2000)}
                className={`px-2 py-1 rounded ${playbackSpeed === 2000 ? 'bg-primary-container text-on-primary-fixed font-bold' : 'bg-surface-container text-outline'}`}
              >
                1x
              </button>
              <button
                onClick={() => setPlaybackSpeed(1000)}
                className={`px-2 py-1 rounded ${playbackSpeed === 1000 ? 'bg-primary-container text-on-primary-fixed font-bold' : 'bg-surface-container text-outline'}`}
              >
                2x
              </button>
              <button
                onClick={() => setPlaybackSpeed(400)}
                className={`px-2 py-1 rounded ${playbackSpeed === 400 ? 'bg-primary-container text-on-primary-fixed font-bold' : 'bg-surface-container text-outline'}`}
              >
                Fast
              </button>
            </div>
          </div>

          {/* Stepped Timeline Progression */}
          <div className="p-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl space-y-4 font-mono">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <h3 className="text-body-md font-bold text-on-surface uppercase">
                Simulated Attack Progression Timeline
              </h3>
              <span className="text-xs text-primary-container font-bold">
                Step {currentStepIndex + 1} of {scenarioData?.steps?.length || 1} &bull; Timestamp: {currentStep.timestamp}
              </span>
            </div>

            <div className="space-y-3">
              {scenarioData?.steps?.map((step, idx) => {
                const isCurrent = idx === currentStepIndex;
                const isPast = idx < currentStepIndex;
                return (
                  <div
                    key={idx}
                    onClick={() => {
                      setIsPlaying(false);
                      setCurrentStepIndex(idx);
                    }}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isCurrent
                        ? 'bg-surface-container border-primary-container shadow-[0_0_15px_rgba(0,229,255,0.2)]'
                        : isPast
                        ? 'bg-surface-container-lowest/60 border-outline-variant/50 text-outline'
                        : 'opacity-40 bg-surface-container-lowest border-outline-variant/20'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-bold text-primary-fixed-dim">
                        [{step.timestamp}] {step.event_label}
                      </span>
                      <span
                        className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                          step.trust_score < 30
                            ? 'bg-error-container text-error'
                            : step.trust_score < 70
                            ? 'bg-amber-950 text-amber-300'
                            : 'bg-emerald-950 text-emerald-400'
                        }`}
                      >
                        Score: {step.trust_score} ({step.action})
                      </span>
                    </div>
                    <p className="text-body-sm text-on-surface font-mono">
                      "{step.transcript}"
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Live Telemetry Gauges (5 Cols) */}
        <div className="xl:col-span-5 space-y-6">
          {/* Real-Time Trust Gauge */}
          <div className="p-5 rounded-xl bg-surface-container-low/85 backdrop-blur-md border border-outline-variant shadow-xl text-center space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60 text-xs font-mono text-outline">
              <span>SIMULATED TRUST SCORE</span>
              <span className="text-primary-container">AUTONOMOUS ATTESTATION</span>
            </div>

            <TrustScoreGauge
              score={currentStep.trust_score}
              riskLevel={currentStep.risk_level}
              isCritical={currentStep.trust_score < 30}
            />

            <div
              className={`p-3 rounded-lg border font-mono text-xs font-bold tracking-wider ${
                currentStep.action === 'BLOCK_TRANSACTION'
                  ? 'bg-error-container/40 border-error text-error animate-pulse'
                  : currentStep.action === 'REQUIRE_MFA'
                  ? 'bg-amber-950/40 border-amber-500 text-amber-300'
                  : 'bg-emerald-950/40 border-emerald-500 text-emerald-400'
              }`}
            >
              AUTONOMOUS DIRECTIVE: {currentStep.action}
            </div>
          </div>

          {/* Real-Time Spectrogram Feed */}
          <div className="p-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl space-y-3 font-mono">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <span className="text-xs font-bold text-on-surface uppercase">Acoustic Glottal Ingress</span>
              <span className="text-xs text-error font-bold">
                {currentStep.voice?.ai_probability ?? 15}% AI Probability
              </span>
            </div>
            <SpectrogramView isLive={true} intensity={currentStep.voice?.ai_probability ?? 15} />
          </div>
        </div>
      </div>
    </div>
  );
}
