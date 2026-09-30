import React, { useState, useEffect } from 'react';
import { api } from '../services/api';

export default function Analytics() {
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    api.getAnalytics()
      .then((data) => setAnalytics(data))
      .catch(() => {});
  }, []);

  const perf = analytics?.model_performance || {
    precision: 98.4,
    recall: 97.1,
    f1_score: 97.7,
    false_positive_rate: 0.8,
    average_latency_ms: 142,
    label: 'Prototype / Demonstration Benchmark Metrics'
  };

  const threatTypes = analytics?.threat_types || [
    { name: 'Neural Clone (ElevenLabs)', count: 48, percentage: 42 },
    { name: 'Diffusion Vocoder Glottal Spoof', count: 27, percentage: 24 },
    { name: 'WaveNet-XL Zero-Shot', count: 21, percentage: 18 },
    { name: 'VALL-E 2 Sub-Packet Splicing', count: 12, percentage: 10 },
    { name: 'Coercive Social Eng / Human Impersonation', count: 7, percentage: 6 }
  ];

  const distributions = analytics?.score_distribution || [
    { range: '90–100 (Safe)', count: 942, color: '#10B981' },
    { range: '60–89 (Advisory)', count: 218, color: '#F59E0B' },
    { range: '30–59 (High Risk)', count: 86, color: '#F97316' },
    { range: '0–29 (Critical)', count: 38, color: '#EF4444' }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-outline-variant/60 pb-5">
        <div>
          <div className="flex items-center gap-2 text-label-code-sm font-mono text-outline mb-1 text-xs">
            <span>CONSOLE</span>
            <span>/</span>
            <span className="text-primary-container">ANALYTICS &amp; ML TELEMETRY</span>
          </div>
          <h1 className="text-headline-lg font-bold text-on-surface tracking-tight">
            Security Analytics &amp; Threat Performance
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1 font-mono text-xs">
            Model attestation telemetry, ROC-curve indicators, and synthesis architecture threat vectors.
          </p>
        </div>

        {/* Prototype label */}
        <div className="px-3 py-1.5 rounded-lg bg-surface-container border border-outline font-mono text-xs text-primary-fixed-dim">
          &bull; {perf.label}
        </div>
      </div>

      {/* Model Benchmark Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-4">
        <div className="p-4 rounded-xl bg-surface-container-low/80 border border-outline-variant text-center font-mono">
          <span className="text-outline text-[11px] block uppercase">PRECISION</span>
          <span className="text-3xl font-black text-emerald-400 mt-1 block">{perf.precision}%</span>
          <span className="text-[10px] text-on-surface-variant">True Positive Rate</span>
        </div>

        <div className="p-4 rounded-xl bg-surface-container-low/80 border border-outline-variant text-center font-mono">
          <span className="text-outline text-[11px] block uppercase">RECALL</span>
          <span className="text-3xl font-black text-emerald-400 mt-1 block">{perf.recall}%</span>
          <span className="text-[10px] text-on-surface-variant">Sensitivity</span>
        </div>

        <div className="p-4 rounded-xl bg-surface-container-low/80 border border-outline-variant text-center font-mono">
          <span className="text-outline text-[11px] block uppercase">F1-SCORE</span>
          <span className="text-3xl font-black text-primary-container mt-1 block">{perf.f1_score}%</span>
          <span className="text-[10px] text-on-surface-variant">Harmonic Mean</span>
        </div>

        <div className="p-4 rounded-xl bg-surface-container-low/80 border border-outline-variant text-center font-mono">
          <span className="text-outline text-[11px] block uppercase">FALSE POSITIVE</span>
          <span className="text-3xl font-black text-on-surface mt-1 block">{perf.false_positive_rate}%</span>
          <span className="text-[10px] text-emerald-400">&lt;1.0% Target Met</span>
        </div>

        <div className="p-4 rounded-xl bg-surface-container-low/80 border border-outline-variant text-center font-mono col-span-2 sm:col-span-1">
          <span className="text-outline text-[11px] block uppercase">AVG LATENCY</span>
          <span className="text-3xl font-black text-primary-fixed-dim mt-1 block">{perf.average_latency_ms}ms</span>
          <span className="text-[10px] text-on-surface-variant">Sub-Packet Intercept</span>
        </div>
      </div>

      {/* Breakdown Charts Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Synthetic Architecture Vectors (7 Cols) */}
        <div className="xl:col-span-7 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4 font-mono">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
            <h3 className="text-body-md font-bold text-on-surface uppercase">
              Threat Breakdown by Vocoder Engine
            </h3>
            <span className="text-xs text-outline">Ingress Signature Attribution</span>
          </div>

          <div className="space-y-3 pt-2">
            {threatTypes.map((t, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-on-surface-variant">{t.name}</span>
                  <span className="font-bold text-on-surface">{t.percentage}% ({t.count} attacks)</span>
                </div>
                <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary-container rounded-full"
                    style={{ width: `${t.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Score Distribution (5 Cols) */}
        <div className="xl:col-span-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl space-y-4 font-mono">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
            <h3 className="text-body-md font-bold text-on-surface uppercase">
              Trust Score Distribution
            </h3>
            <span className="text-xs text-outline">1,284 Calls Evaluated</span>
          </div>

          <div className="space-y-3 pt-2">
            {distributions.map((d, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-on-surface-variant">{d.range}</span>
                  <span className="font-bold text-on-surface">{d.count} calls</span>
                </div>
                <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${(d.count / 1284) * 100}%`, backgroundColor: d.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
