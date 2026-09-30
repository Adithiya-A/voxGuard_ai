import React, { useState } from 'react';

export default function ActionModal({ isOpen, onClose, callId, onConfirm, defaultAction = 'BLOCK_TRANSACTION' }) {
  const [selectedAction, setSelectedAction] = useState(defaultAction);
  const [reason, setReason] = useState('AI voice clone detected with ₹25,00,000 transfer directive');

  if (!isOpen) return null;

  const actions = [
    { id: 'BLOCK_TRANSACTION', label: 'Block Transaction & Quarantine', icon: 'block', desc: 'Immediately prevents capital movement and severs telephony ingress.' },
    { id: 'REQUIRE_MFA', label: 'Require Out-of-Band Secondary MFA', icon: 'phonelink_lock', desc: 'Dispatches FIDO2/WebAuthn push challenge to registered employee device.' },
    { id: 'INDEPENDENT_CALLBACK', label: 'Dispatch Independent Callback', icon: 'call_split', desc: 'Disconnects and dials enrolled enterprise telephony extension directly.' },
    { id: 'CONTINUE_MONITORING', label: 'Continue Passive Surveillance', icon: 'visibility', desc: 'Allows call to proceed while recording high-frequency acoustic telemetry.' }
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm(selectedAction, reason);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-surface-container-lowest/80 backdrop-blur-md">
      <div className="bg-surface-container-low border border-outline-variant w-full max-w-xl rounded-2xl p-6 shadow-2xl relative overflow-hidden">
        <div className="flex items-center justify-between pb-4 border-b border-outline-variant/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-error-container/30 border border-error/50 flex items-center justify-center text-error">
              <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                security_update_warning
              </span>
            </div>
            <div>
              <h3 className="text-headline-sm font-bold text-on-surface">Enforce Preventive Defense Action</h3>
              <p className="text-label-code-sm font-mono text-outline">Target Call Session: {callId}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-outline hover:text-on-surface p-1 rounded">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div className="space-y-2">
            <label className="text-label-code-sm font-mono text-outline uppercase text-xs">Select Preventive Action</label>
            <div className="space-y-2">
              {actions.map((act) => (
                <div
                  key={act.id}
                  onClick={() => setSelectedAction(act.id)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-start gap-3 ${
                    selectedAction === act.id
                      ? 'bg-surface-container border-primary-container/80 shadow-[0_0_15px_rgba(0,229,255,0.15)]'
                      : 'bg-surface-container-lowest/60 border-outline-variant/60 hover:border-outline'
                  }`}
                >
                  <span className={`material-symbols-outlined text-xl mt-0.5 ${selectedAction === act.id ? 'text-primary-container' : 'text-outline'}`}>
                    {act.icon}
                  </span>
                  <div className="flex-1">
                    <div className="text-body-sm font-semibold text-on-surface">{act.label}</div>
                    <div className="text-xs text-on-surface-variant mt-0.5">{act.desc}</div>
                  </div>
                  <input
                    type="radio"
                    name="action"
                    checked={selectedAction === act.id}
                    onChange={() => setSelectedAction(act.id)}
                    className="accent-primary-container mt-1"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-1.5 pt-2">
            <label className="text-label-code-sm font-mono text-outline uppercase text-xs">Forensic Justification / Incident Memo</label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full bg-surface-container-lowest border border-outline-variant rounded-xl p-3 text-body-sm text-on-surface focus:border-primary-container focus:outline-none font-mono"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-outline-variant/60">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-surface-container border border-outline-variant text-on-surface hover:bg-surface-container-high text-xs font-mono"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-lg bg-primary-container text-on-primary-fixed hover:bg-primary text-xs font-mono font-bold tracking-wider transition-all shadow-[0_0_15px_rgba(0,229,255,0.3)] active:scale-95"
            >
              ENFORCE MITIGATION
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
