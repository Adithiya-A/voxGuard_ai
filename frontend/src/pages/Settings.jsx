import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function Settings() {
  const { addNotification } = useApp();
  const [weights, setWeights] = useState({
    voice_synthetic: 0.30,
    speaker_anomaly: 0.18,
    prosody_anomaly: 0.10,
    conversation_risk: 0.20,
    caller_risk: 0.07,
    transaction_risk: 0.15,
  });
  const [policies, setPolicies] = useState([]);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    api.getSettings()
      .then((data) => {
        if (data.weights) setWeights(data.weights);
        if (data.policies) setPolicies(data.policies);
      })
      .catch(() => {});
  }, []);

  const handleWeightChange = (key, val) => {
    setWeights((prev) => ({ ...prev, [key]: parseFloat(val) }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      await api.updateWeights(weights);
      setIsSaved(true);
      addNotification({
        type: 'safe',
        title: 'POLICY MATRIX UPDATED',
        message: 'New multi-signal weights active in SOC Trust Engine.'
      });
      setTimeout(() => setIsSaved(false), 3000);
    } catch (err) {
      console.warn("Local update of weights");
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-outline-variant/60 pb-5">
        <div>
          <div className="flex items-center gap-2 text-label-code-sm font-mono text-outline mb-1 text-xs">
            <span>CONSOLE</span>
            <span>/</span>
            <span className="text-primary-container">POLICY MATRIX</span>
          </div>
          <h1 className="text-headline-lg font-bold text-on-surface tracking-tight">
            Security Settings &amp; Trust Weights Matrix
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1 font-mono text-xs">
            Tune multi-signal weighting coefficients, risk cutoffs, and autonomous PBX wiretap policies.
          </p>
        </div>

        <button
          onClick={handleSave}
          className="px-5 py-2.5 rounded-lg bg-primary-container text-on-primary-fixed hover:bg-primary font-mono text-xs font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(0,229,255,0.3)]"
        >
          <span className="material-symbols-outlined text-base">save</span>
          <span>{isSaved ? 'POLICY APPLIED!' : 'SAVE & DEPLOY POLICIES'}</span>
        </button>
      </div>

      {/* Grid: Weights Sliders (6 Cols) & Policy Rules Table (6 Cols) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left Column: Trust Engine Weight Sliders */}
        <div className="xl:col-span-6 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-5 font-mono">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
            <h3 className="text-body-md font-bold text-on-surface uppercase">
              Trust Score Signal Weights (Total: 100%)
            </h3>
            <span className="text-primary-container text-xs">Deterministic Model</span>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-on-surface-variant">Voice Synthetic Risk (Acoustic/Spectral):</span>
                <span className="text-primary-container font-bold">{Math.round(weights.voice_synthetic * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.6"
                step="0.01"
                value={weights.voice_synthetic}
                onChange={(e) => handleWeightChange('voice_synthetic', e.target.value)}
                className="w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary-container"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-on-surface-variant">Speaker Anomaly (Clone Vector):</span>
                <span className="text-primary-container font-bold">{Math.round(weights.speaker_anomaly * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.4"
                step="0.01"
                value={weights.speaker_anomaly}
                onChange={(e) => handleWeightChange('speaker_anomaly', e.target.value)}
                className="w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary-container"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-on-surface-variant">Conversation Coercion Risk (Gemini/NLP):</span>
                <span className="text-primary-container font-bold">{Math.round(weights.conversation_risk * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.4"
                step="0.01"
                value={weights.conversation_risk}
                onChange={(e) => handleWeightChange('conversation_risk', e.target.value)}
                className="w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary-container"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-on-surface-variant">Transaction Exposure Risk:</span>
                <span className="text-primary-container font-bold">{Math.round(weights.transaction_risk * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.4"
                step="0.01"
                value={weights.transaction_risk}
                onChange={(e) => handleWeightChange('transaction_risk', e.target.value)}
                className="w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary-container"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-on-surface-variant">Prosody &amp; Stress Dynamics:</span>
                <span className="text-primary-container font-bold">{Math.round(weights.prosody_anomaly * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.3"
                step="0.01"
                value={weights.prosody_anomaly}
                onChange={(e) => handleWeightChange('prosody_anomaly', e.target.value)}
                className="w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary-container"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-on-surface-variant">Caller Trunk Provenance:</span>
                <span className="text-primary-container font-bold">{Math.round(weights.caller_risk * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.2"
                step="0.01"
                value={weights.caller_risk}
                onChange={(e) => handleWeightChange('caller_risk', e.target.value)}
                className="w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary-container"
              />
            </div>
          </div>
        </div>

        {/* Right Column: Autonomous Policies */}
        <div className="xl:col-span-6 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4 font-mono">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
            <h3 className="text-body-md font-bold text-on-surface uppercase">
              Autonomous Trigger Policies
            </h3>
            <span className="text-xs text-outline">Real-Time Rule Engine</span>
          </div>

          <div className="space-y-3 pt-1">
            {policies.map((p) => (
              <div key={p.id} className="p-3 rounded-lg bg-surface-container border border-outline-variant/50 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-primary-fixed-dim">{p.id}: {p.name}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${p.severity === 'CRITICAL' ? 'bg-error-container text-error' : 'bg-amber-950 text-amber-300'}`}>
                    {p.action}
                  </span>
                </div>
                <div className="text-[11px] text-outline font-mono">
                  Rule Condition: {p.condition}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
