import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function Incidents() {
  const navigate = useNavigate();
  const { addNotification } = useApp();
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);

  useEffect(() => {
    loadIncidents();
  }, []);

  const loadIncidents = async () => {
    try {
      const data = await api.getIncidents();
      setIncidents(data);
      if (data.length) setSelectedIncident(data[0]);
    } catch (e) {
      console.warn("Using fallback incidents");
    }
  };

  const handleAction = async (incidentId, action) => {
    try {
      await api.incidentAction(incidentId, action, `Action enforced by SOC Commander`);
      addNotification({
        type: action === 'BLOCK_TRANSACTION' ? 'critical' : 'warning',
        title: `INCIDENT ${incidentId} UPDATED`,
        message: `Preventive directive ${action} applied successfully.`
      });
      loadIncidents();
    } catch (e) {
      console.warn("Local update of incident action");
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
            <span className="text-primary-container">THREAT RESPONSE</span>
          </div>
          <h1 className="text-headline-lg font-bold text-on-surface tracking-tight flex items-center gap-3">
            <span>Incident Response &amp; Mitigation Dispatch</span>
            <span className="px-2.5 py-0.5 rounded bg-error-container text-error font-mono text-xs font-bold">
              {incidents.length} ACTIVE INCIDENTS
            </span>
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1 font-mono text-xs">
            Rapid mitigation workbench for confirmed AI voice impersonations and fraudulent capital movement attempts.
          </p>
        </div>
      </div>

      {/* Bento Grid: Incident List (7 Cols) & Detail / Action Panel (5 Cols) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left Column: Incidents Queue */}
        <div className="xl:col-span-7 space-y-4">
          {incidents.map((inc) => {
            const isSelected = selectedIncident?.incident_id === inc.incident_id;
            const isCritical = inc.severity === 'CRITICAL';
            return (
              <div
                key={inc.incident_id}
                onClick={() => setSelectedIncident(inc)}
                className={`p-5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-surface-container border-primary-container shadow-[0_0_20px_rgba(0,229,255,0.15)]'
                    : 'bg-surface-container-low/75 border-outline-variant hover:border-outline'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <span
                      className={`material-symbols-outlined text-2xl ${
                        isCritical ? 'text-error' : 'text-amber-400'
                      }`}
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      {isCritical ? 'gshield' : 'warning'}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-on-surface font-mono">{inc.incident_id}</span>
                        <span
                          className={`px-2 py-0.2 rounded text-[10px] font-mono font-bold ${
                            isCritical ? 'bg-error-container text-error' : 'bg-amber-950 text-amber-300'
                          }`}
                        >
                          {inc.severity}
                        </span>
                      </div>
                      <div className="text-xs font-mono text-outline mt-0.5">
                        Call Session: {inc.call_id} &bull; Target: {inc.claimed_identity}
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-xs font-mono font-bold text-error px-2 py-1 rounded bg-error-container/20 border border-error/30">
                      Trust: {inc.trust_score}/100
                    </span>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-outline-variant/40 flex items-center justify-between text-xs font-mono">
                  <span className="text-on-surface-variant font-semibold">
                    Threat: {inc.threat_label}
                  </span>
                  <span className="text-primary-container font-bold">
                    Action: {inc.current_action}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Column: Detailed Forensic Actions */}
        <div className="xl:col-span-5">
          {selectedIncident ? (
            <div className="p-5 rounded-xl bg-surface-container-low/85 backdrop-blur-md border border-outline-variant shadow-2xl space-y-5 sticky top-20">
              <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
                <div>
                  <h3 className="text-headline-sm font-bold text-on-surface font-mono">
                    {selectedIncident.incident_id}
                  </h3>
                  <p className="text-xs font-mono text-outline">{selectedIncident.threat_label}</p>
                </div>
                <button
                  onClick={() => navigate(`/investigation/${selectedIncident.call_id}`)}
                  className="text-xs font-mono text-primary-container hover:underline"
                >
                  Full Dossier &rarr;
                </button>
              </div>

              {/* Multi-Factor Forensic Metrics */}
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between p-2.5 rounded bg-surface-container">
                  <span className="text-outline">Target Identity:</span>
                  <span className="font-bold text-on-surface">{selectedIncident.claimed_identity}</span>
                </div>
                <div className="flex justify-between p-2.5 rounded bg-surface-container">
                  <span className="text-outline">Synthetic AI Probability:</span>
                  <span className="font-bold text-error">{selectedIncident.ai_probability}%</span>
                </div>
                <div className="flex justify-between p-2.5 rounded bg-surface-container">
                  <span className="text-outline">Speaker Cosine Similarity:</span>
                  <span className="font-bold text-emerald-400">{selectedIncident.speaker_similarity}%</span>
                </div>
                <div className="flex justify-between p-2.5 rounded bg-surface-container">
                  <span className="text-outline">Conversational Coercion:</span>
                  <span className="font-bold text-error">{selectedIncident.conversation_risk}%</span>
                </div>
                <div className="flex justify-between p-2.5 rounded bg-surface-container">
                  <span className="text-outline">Target Beneficiary Account:</span>
                  <span className="font-bold text-amber-400">{selectedIncident.target_account}</span>
                </div>
                <div className="flex justify-between p-2.5 rounded bg-surface-container">
                  <span className="text-outline">Capital Exposure:</span>
                  <span className="font-bold text-error text-sm">{selectedIncident.amount}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-2 border-t border-outline-variant/60">
                <span className="text-label-code-sm font-mono text-outline uppercase text-[11px] block">
                  Enforce Immediate Mitigation
                </span>

                <button
                  onClick={() => handleAction(selectedIncident.incident_id, 'BLOCK_TRANSACTION')}
                  className="w-full py-2.5 px-3 rounded-lg bg-error-container hover:bg-error/30 text-on-error-container border border-error/80 font-mono text-xs font-bold tracking-wider flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(239,68,68,0.3)]"
                >
                  <span className="material-symbols-outlined text-base">block</span>
                  <span>BLOCK CAPITAL MOVEMENT</span>
                </button>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleAction(selectedIncident.incident_id, 'REQUIRE_MFA')}
                    className="py-2 px-3 rounded-lg bg-surface-container border border-outline hover:border-primary-container text-on-surface font-mono text-xs flex items-center justify-center gap-1.5"
                  >
                    <span className="material-symbols-outlined text-base text-primary-container">phonelink_lock</span>
                    <span>Push MFA</span>
                  </button>
                  <button
                    onClick={() => handleAction(selectedIncident.incident_id, 'INDEPENDENT_CALLBACK')}
                    className="py-2 px-3 rounded-lg bg-surface-container border border-outline hover:border-primary-container text-on-surface font-mono text-xs flex items-center justify-center gap-1.5"
                  >
                    <span className="material-symbols-outlined text-base text-secondary">call_split</span>
                    <span>Callback</span>
                  </button>
                </div>

                <button
                  onClick={() => handleAction(selectedIncident.incident_id, 'RESOLVE')}
                  className="w-full py-2 px-3 rounded-lg bg-surface-container-high border border-outline-variant hover:border-emerald-500/50 text-emerald-400 font-mono text-xs flex items-center justify-center gap-1.5 mt-2"
                >
                  <span className="material-symbols-outlined text-base">check_circle</span>
                  <span>Mark Incident Mitigated &amp; Close</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="p-8 rounded-xl bg-surface-container-low border border-outline-variant text-center font-mono text-xs text-outline">
              Select an incident from queue to triage
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
