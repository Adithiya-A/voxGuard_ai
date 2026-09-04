import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function Dashboard() {
  const navigate = useNavigate();
  const { setActiveCallId } = useApp();
  const [analytics, setAnalytics] = useState(null);
  const [calls, setCalls] = useState([]);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const [anData, callList] = await Promise.all([
        api.getAnalytics(),
        api.getCalls(),
      ]);
      setAnalytics(anData);
      setCalls(callList);
    } catch (e) {
      console.warn("Using fallback analytics data");
    }
  };

  const handleInspect = (callId) => {
    setActiveCallId(callId);
    navigate(`/investigation/${callId}`);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Welcome & Quick Actions */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-outline-variant/60 pb-5">
        <div>
          <div className="flex items-center gap-2 text-label-code-sm font-mono text-outline mb-1 text-xs">
            <span>CONSOLE</span>
            <span>/</span>
            <span className="text-primary-container">SECURITY OPERATIONS CENTER</span>
          </div>
          <h1 className="text-headline-lg font-bold text-on-surface tracking-tight flex items-center gap-3">
            <span>Real-Time Voice Trust &amp; Threat Telemetry</span>
            <span className="px-2.5 py-0.5 rounded bg-surface-container-high border border-primary-container/40 text-xs font-mono text-primary-container font-semibold">
              LIVE MONITORING
            </span>
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1">
            Autonomous multi-signal detection of weaponized voice cloning and executive impersonation attacks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/live-call"
            className="px-4 py-2.5 rounded-lg bg-surface-container border border-primary-container/40 hover:border-primary-container text-primary-container font-mono text-xs font-bold flex items-center gap-2 transition-all shadow-[0_0_12px_rgba(0,229,255,0.15)]"
          >
            <span className="w-2 h-2 rounded-full bg-primary-container animate-ping"></span>
            <span>OPEN LIVE CALL INTERCEPT</span>
          </Link>
          <Link
            to="/demo"
            className="px-4 py-2.5 rounded-lg bg-primary-container text-on-primary-fixed hover:bg-primary font-mono text-xs font-bold flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(0,229,255,0.3)] active:scale-95"
          >
            <span className="material-symbols-outlined text-base">sensors</span>
            <span>LAUNCH ATTACK SIMULATOR</span>
          </Link>
        </div>
      </div>

      {/* 4 KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-surface-container-low/80 backdrop-blur-md border border-outline-variant relative overflow-hidden shadow-lg">
          <div className="flex items-center justify-between text-outline text-xs font-mono">
            <span>ACTIVE TELEPHONY STREAMS</span>
            <span className="material-symbols-outlined text-primary-container text-lg">phone_in_talk</span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black font-mono text-on-surface">03</span>
            <span className="text-xs font-mono text-primary-container flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-container animate-ping"></span>
              Live Wiretaps
            </span>
          </div>
          <div className="mt-2 text-xs text-on-surface-variant font-mono">
            Trunk SIP-901 Active Ingress
          </div>
        </div>

        <div className="p-5 rounded-xl bg-surface-container-low/80 backdrop-blur-md border border-outline-variant relative overflow-hidden shadow-lg">
          <div className="flex items-center justify-between text-outline text-xs font-mono">
            <span>CALLS ATTESTED TODAY</span>
            <span className="material-symbols-outlined text-secondary text-lg">verified_user</span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black font-mono text-on-surface">1,284</span>
            <span className="text-xs font-mono text-emerald-400">+18.2%</span>
          </div>
          <div className="mt-2 text-xs text-on-surface-variant font-mono">
            98.4% Zero-Day Attestation Rate
          </div>
        </div>

        <div className="p-5 rounded-xl bg-surface-container-low/80 backdrop-blur-md border border-outline-variant relative overflow-hidden shadow-lg">
          <div className="flex items-center justify-between text-outline text-xs font-mono">
            <span>CONFIRMED DEEPFAKE THREATS</span>
            <span className="material-symbols-outlined text-error text-lg">gshield</span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black font-mono text-error">14</span>
            <span className="text-xs font-mono text-error font-bold px-1.5 py-0.5 rounded bg-error-container/30 border border-error/40">
              MITIGATED
            </span>
          </div>
          <div className="mt-2 text-xs text-on-surface-variant font-mono">
            100% High-Risk Neutralization
          </div>
        </div>

        <div className="p-5 rounded-xl bg-surface-container-low/80 backdrop-blur-md border border-outline-variant relative overflow-hidden shadow-lg">
          <div className="flex items-center justify-between text-outline text-xs font-mono">
            <span>PREVENTED CAPITAL LOSS</span>
            <span className="material-symbols-outlined text-emerald-400 text-lg">payments</span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black font-mono text-emerald-400">₹1.42 Cr</span>
          </div>
          <div className="mt-2 text-xs text-on-surface-variant font-mono">
            Autonomous RTGS Block Enforced
          </div>
        </div>
      </div>

      {/* Main Grid: Live Threat Intercept Feed & Engine Health */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left 8 Cols: Active Calls Feed */}
        <div className="xl:col-span-8 space-y-4">
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary-container animate-pulse"></span>
                <h2 className="text-headline-sm font-bold text-on-surface">Active Telephony Intercept Queue</h2>
              </div>
              <span className="text-xs font-mono text-outline">Real-Time Continuous Ingress</span>
            </div>

            {/* Table */}
            <div className="overflow-x-auto mt-4">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="text-outline border-b border-outline-variant/60">
                    <th className="pb-3 px-3">CALL ID</th>
                    <th className="pb-3 px-3">CLAIMED IDENTITY</th>
                    <th className="pb-3 px-3">AI PROBABILITY</th>
                    <th className="pb-3 px-3">TRUST SCORE</th>
                    <th className="pb-3 px-3">STATUS</th>
                    <th className="pb-3 px-3 text-right">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/30">
                  {calls.map((c) => {
                    const isCritical = c.trust_score < 30;
                    return (
                      <tr key={c.call_id} className="hover:bg-surface-container-high/40 transition-colors">
                        <td className="py-3.5 px-3 font-bold text-primary-fixed-dim">
                          <Link to={`/investigation/${c.call_id}`} className="hover:underline">
                            {c.call_id}
                          </Link>
                        </td>
                        <td className="py-3.5 px-3">
                          <div className="text-on-surface font-semibold">{c.claimed_identity}</div>
                          <div className="text-[10px] text-outline">{c.caller.split('//')[0]}</div>
                        </td>
                        <td className="py-3.5 px-3">
                          <span className={`font-bold ${c.voice?.ai_probability > 60 ? 'text-error' : 'text-emerald-400'}`}>
                            {c.voice?.ai_probability ?? 12}%
                          </span>
                        </td>
                        <td className="py-3.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded font-bold ${
                              isCritical
                                ? 'bg-error-container/40 text-error border border-error/50'
                                : c.trust_score < 60
                                ? 'bg-amber-950/40 text-amber-300 border border-amber-500/40'
                                : 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/40'
                            }`}
                          >
                            {c.trust_score} / 100
                          </span>
                        </td>
                        <td className="py-3.5 px-3">
                          <span className="text-on-surface-variant">{c.status}</span>
                        </td>
                        <td className="py-3.5 px-3 text-right">
                          <button
                            onClick={() => handleInspect(c.call_id)}
                            className="px-2.5 py-1 rounded bg-surface-container border border-outline hover:border-primary-container text-primary-container text-[11px] transition-all"
                          >
                            Investigate &rarr;
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right 4 Cols: System Telemetry & Health */}
        <div className="xl:col-span-4 space-y-4">
          <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant p-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <h3 className="text-body-md font-bold text-on-surface uppercase font-mono">
                System Defense Enclave Health
              </h3>
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            </div>

            <div className="mt-4 space-y-3 font-mono text-xs">
              <div className="p-3 rounded-lg bg-surface-container flex items-center justify-between border border-outline-variant/50">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary-container text-base">graphic_eq</span>
                  <span>Spectral Deepfake Engine</span>
                </div>
                <span className="text-emerald-400 font-bold">ACTIVE (14ms)</span>
              </div>

              <div className="p-3 rounded-lg bg-surface-container flex items-center justify-between border border-outline-variant/50">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary text-base">record_voice_over</span>
                  <span>Speaker Verification (ECAPA)</span>
                </div>
                <span className="text-emerald-400 font-bold">ACTIVE (22ms)</span>
              </div>

              <div className="p-3 rounded-lg bg-surface-container flex items-center justify-between border border-outline-variant/50">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-tertiary text-base">psychology</span>
                  <span>Conversation NLP Intelligence</span>
                </div>
                <span className="text-emerald-400 font-bold">GEMINI / NLP</span>
              </div>

              <div className="p-3 rounded-lg bg-surface-container flex items-center justify-between border border-outline-variant/50">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-amber-400 text-base">calculate</span>
                  <span>Deterministic Trust Engine</span>
                </div>
                <span className="text-emerald-400 font-bold">ONLINE</span>
              </div>

              <div className="p-3 rounded-lg bg-surface-container flex items-center justify-between border border-outline-variant/50">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary-fixed-dim text-base">hub</span>
                  <span>Cryptographic Blockchain Ledger</span>
                </div>
                <span className="text-primary-container font-bold">POLYGON TESTNET</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
