import React from 'react';

export default function TrustScoreGauge({ score = 82, riskLevel = 'WARNING', isCritical = false }) {
  // Score interpolation
  const getColor = (s) => {
    if (s >= 90) return { stroke: '#10b981', text: 'text-emerald-400', bg: 'rgba(16, 185, 129, 0.1)', glow: 'rgba(16, 185, 129, 0.3)' };
    if (s >= 60) return { stroke: '#f59e0b', text: 'text-amber-400', bg: 'rgba(245, 158, 11, 0.1)', glow: 'rgba(245, 158, 11, 0.3)' };
    if (s >= 30) return { stroke: '#f97316', text: 'text-orange-400', bg: 'rgba(249, 115, 22, 0.1)', glow: 'rgba(249, 115, 22, 0.3)' };
    return { stroke: '#ef4444', text: 'text-error', bg: 'rgba(239, 68, 68, 0.15)', glow: 'rgba(239, 68, 68, 0.4)' };
  };

  const theme = getColor(score);
  const radius = 64;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="relative flex flex-col items-center justify-center p-4">
      {/* Glow aura */}
      <div
        className="absolute inset-0 rounded-full blur-2xl transition-all duration-700 pointer-events-none"
        style={{ background: theme.glow }}
      />

      {/* SVG Arc Gauge */}
      <div className="relative w-44 h-44 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
          {/* Background Track */}
          <circle
            cx="80"
            cy="80"
            r={radius}
            className="stroke-surface-container-highest/60"
            strokeWidth="10"
            fill="transparent"
          />
          {/* Active Dynamic Progress Ring */}
          <circle
            cx="80"
            cy="80"
            r={radius}
            stroke={theme.stroke}
            strokeWidth="10"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            fill="transparent"
            className="transition-all duration-700 ease-out"
          />
        </svg>

        {/* Center Readout */}
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className={`text-5xl font-black font-mono tracking-tight tabular-nums transition-colors duration-500 ${theme.text}`}>
            {score < 10 ? `0${score}` : score}
          </span>
          <span className="text-label-code-sm font-mono text-outline text-[11px] uppercase tracking-wider mt-0.5">
            / 100 TRUST
          </span>
        </div>
      </div>

      {/* Risk Badge Pill */}
      <div className="mt-3">
        <span
          className={`px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider border transition-all duration-500 ${
            score < 30
              ? 'bg-error-container/40 border-error text-error shadow-[0_0_12px_rgba(239,68,68,0.3)] animate-pulse'
              : score < 60
              ? 'bg-amber-950/40 border-amber-500/60 text-amber-300'
              : score < 90
              ? 'bg-surface-container border-outline text-primary-fixed-dim'
              : 'bg-emerald-950/40 border-emerald-500/60 text-emerald-400'
          }`}
        >
          {riskLevel} RISK
        </span>
      </div>
    </div>
  );
}
