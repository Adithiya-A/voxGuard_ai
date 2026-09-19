import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

export default function CallHistory() {
  const navigate = useNavigate();
  const [calls, setCalls] = useState([]);
  const [filter, setFilter] = useState('ALL');
  const [modeFilter, setModeFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  const fetchCallsList = () => {
    api.getCalls()
      .then((data) => setCalls(data))
      .catch(() => {});
  };

  useEffect(() => {
    fetchCallsList();
  }, []);

  const realCallsCount = calls.filter((c) => (c.mode === 'REAL' || c.call_id?.startsWith('VS-LIVE-'))).length;
  const demoCallsCount = calls.length - realCallsCount;

  const filteredCalls = calls.filter((c) => {
    const isReal = (c.mode === 'REAL' || c.call_id?.startsWith('VS-LIVE-'));
    if (modeFilter === 'REAL' && !isReal) return false;
    if (modeFilter === 'DEMO' && isReal) return false;

    const matchesSearch =
      (c.call_id || '').toLowerCase().includes(search.toLowerCase()) ||
      (c.claimed_identity || '').toLowerCase().includes(search.toLowerCase()) ||
      (c.caller || '').toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;
    if (filter === 'ALL') return true;
    if (filter === 'SAFE') return c.trust_score >= 90;
    if (filter === 'SUSPICIOUS') return c.trust_score >= 60 && c.trust_score < 90;
    if (filter === 'HIGH_RISK') return c.trust_score >= 30 && c.trust_score < 60;
    if (filter === 'CRITICAL') return c.trust_score < 30;
    if (filter === 'BLOCKED') return c.status === 'BLOCKED';
    return true;
  });

  const filterTabs = [
    { id: 'ALL', label: 'All Severity' },
    { id: 'CRITICAL', label: 'Critical Attacks' },
    { id: 'BLOCKED', label: 'Blocked' },
    { id: 'HIGH_RISK', label: 'High Risk' },
    { id: 'SUSPICIOUS', label: 'Advisory Warning' },
    { id: 'SAFE', label: 'Attested Safe' }
  ];

  const modeTabs = [
    { id: 'ALL', label: `All Sources (${calls.length})` },
    { id: 'REAL', label: `Real Microphones (${realCallsCount})` },
    { id: 'DEMO', label: `Demo Scenarios (${demoCallsCount})` }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-outline-variant/60 pb-5">
        <div>
          <div className="flex items-center gap-2 text-label-code-sm font-mono text-outline mb-1 text-xs">
            <span>CONSOLE</span>
            <span>/</span>
            <span className="text-primary-container">FORENSIC ARCHIVE</span>
          </div>
          <h1 className="text-headline-lg font-bold text-on-surface tracking-tight">
            Telephony Attestation &amp; Call History
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1 font-mono text-xs">
            Persistent local SQLite audit trail ({realCallsCount} real live captures, {demoCallsCount} demo scenarios).
          </p>
        </div>

        {/* Search Bar & Refresh */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="w-full sm:w-80 relative">
            <input
              type="text"
              placeholder="Search Call ID, Caller, or Identity..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-surface-container-low border border-outline-variant rounded-lg pl-9 pr-4 py-2 text-xs font-mono text-on-surface focus:border-primary-container focus:outline-none"
            />
            <span className="material-symbols-outlined text-outline absolute left-2.5 top-2 text-lg">
              search
            </span>
          </div>
          <button
            onClick={fetchCallsList}
            className="p-2 rounded-lg bg-surface-container border border-outline-variant hover:border-primary-container text-on-surface font-mono text-xs flex items-center gap-1 transition-all"
            title="Refresh database records"
          >
            <span className="material-symbols-outlined text-base">refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs Ribbon (Mode and Severity) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Source Mode Selector */}
        <div className="flex flex-wrap items-center gap-2 p-1 rounded-xl bg-surface-container-low border border-outline-variant/60">
          {modeTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setModeFilter(tab.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono transition-all ${
                modeFilter === tab.id
                  ? tab.id === 'REAL'
                    ? 'bg-emerald-600 text-white font-bold shadow-[0_0_12px_rgba(16,185,129,0.35)]'
                    : tab.id === 'DEMO'
                    ? 'bg-purple-700 text-white font-bold shadow-[0_0_12px_rgba(147,51,234,0.35)]'
                    : 'bg-primary-container text-on-primary-fixed font-bold shadow-[0_0_12px_rgba(0,229,255,0.3)]'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Severity Filter */}
        <div className="flex flex-wrap items-center gap-1.5">
          {filterTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1 rounded-full text-xs font-mono transition-all ${
                filter === tab.id
                  ? 'bg-surface-container-high text-primary-container border border-primary-container/60 font-bold'
                  : 'bg-surface-container border border-outline-variant/40 text-outline hover:border-outline hover:text-on-surface'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Table */}
      <div className="rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="text-outline border-b border-outline-variant/60 bg-surface-container-lowest/60">
                <th className="py-3 px-4">CALL ID &amp; SOURCE</th>
                <th className="py-3 px-4">TIMESTAMP</th>
                <th className="py-3 px-4">CALLER ORIGIN</th>
                <th className="py-3 px-4">CLAIMED IDENTITY</th>
                <th className="py-3 px-4">AI PROBABILITY</th>
                <th className="py-3 px-4">TRUST SCORE</th>
                <th className="py-3 px-4">STATUS</th>
                <th className="py-3 px-4 text-right">DOSSIER</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30">
              {filteredCalls.length === 0 ? (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-outline font-mono">
                    No calls match the selected filters.
                  </td>
                </tr>
              ) : (
                filteredCalls.map((c) => {
                  const isCritical = c.trust_score < 30;
                  const isReal = (c.mode === 'REAL' || c.call_id?.startsWith('VS-LIVE-'));
                  return (
                    <tr
                      key={c.call_id}
                      onClick={() => navigate(`/investigation/${c.call_id}`)}
                      className="hover:bg-surface-container-high/50 cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 px-4 font-bold text-primary-fixed-dim">
                        <div className="flex items-center gap-2">
                          <span>{c.call_id}</span>
                          <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                            isReal
                              ? 'bg-emerald-950/90 border border-emerald-500/60 text-emerald-300'
                              : 'bg-purple-950/80 border border-purple-500/60 text-purple-300'
                          }`}>
                            {isReal ? 'REAL' : 'DEMO'}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-on-surface-variant">
                        {c.started_at ? c.started_at.replace('T', ' ').replace('Z', ' UTC') : '2026-09-04'}
                      </td>
                      <td className="py-3.5 px-4 text-on-surface">
                        {c.caller ? c.caller.split('//')[0] : 'Microphone Stream'}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-on-surface">{c.claimed_identity}</div>
                        <div className="text-[10px] text-outline">{c.claimed_role}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`font-bold ${c.voice?.ai_probability > 60 ? 'text-error' : 'text-emerald-400'}`}>
                          {c.voice?.ai_probability ?? 14}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded font-bold ${
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
                      <td className="py-3.5 px-4">
                        <span className="text-on-surface-variant font-semibold">
                          {c.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <span className="text-primary-container hover:underline text-[11px] font-bold">
                          Inspect &rarr;
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

