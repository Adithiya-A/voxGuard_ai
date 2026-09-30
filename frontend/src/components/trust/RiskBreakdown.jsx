import React from 'react';

export default function RiskBreakdown({ breakdown = {} }) {
  const signals = [
    { key: 'voice', label: 'Voice Authenticity (AI Prob)', weight: '30%', value: breakdown.voice_synthetic_risk ?? 87, invert: true },
    { key: 'speaker', label: 'Speaker Anomaly (Clone Vector)', weight: '18%', value: breakdown.speaker_anomaly ?? 85, invert: true },
    { key: 'conversation', label: 'Conversation Coercion (BEC)', weight: '20%', value: breakdown.conversation_risk ?? 91, invert: true },
    { key: 'transaction', label: 'Transaction Exposure Risk', weight: '15%', value: breakdown.transaction_risk ?? 95, invert: true },
    { key: 'prosody', label: 'Prosodic Stress & Jitter', weight: '10%', value: breakdown.prosody_anomaly ?? 72, invert: true },
    { key: 'caller', label: 'Caller Trunk / Provenance', weight: '7%', value: breakdown.caller_risk ?? 85, invert: true },
  ];

  const getBarColor = (val) => {
    if (val >= 70) return 'bg-error shadow-[0_0_8px_#ef4444]';
    if (val >= 40) return 'bg-amber-400';
    return 'bg-emerald-400';
  };

  return (
    <div className="space-y-3">
      {signals.map((sig) => (
        <div key={sig.key} className="space-y-1">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-on-surface-variant flex items-center gap-1.5">
              <span>{sig.label}</span>
              <span className="text-outline text-[10px]">[{sig.weight}]</span>
            </span>
            <span className="font-bold text-on-surface tabular-nums">
              {Math.round(sig.value)}%
            </span>
          </div>
          <div className="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ease-out ${getBarColor(sig.value)}`}
              style={{ width: `${Math.min(100, Math.max(2, sig.value))}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
