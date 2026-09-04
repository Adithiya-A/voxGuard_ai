import React from 'react';
import { useApp } from '../../context/AppContext';

export default function AlertBanner() {
  const { notifications } = useApp();

  if (!notifications.length) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-md w-full pointer-events-none">
      {notifications.map((n) => {
        const isCritical = n.type === 'critical';
        const isSafe = n.type === 'safe';
        return (
          <div
            key={n.id}
            className={`pointer-events-auto p-4 rounded-xl border backdrop-blur-xl shadow-2xl transition-all animate-bounce-short ${
              isCritical
                ? 'bg-error-container/95 border-error text-on-error-container shadow-[0_0_24px_rgba(239,68,68,0.4)]'
                : isSafe
                ? 'bg-surface-container-high border-emerald-500/60 text-emerald-400'
                : 'bg-surface-container-high border-amber-500/60 text-amber-300'
            }`}
          >
            <div className="flex items-start gap-3">
              <span
                className="material-symbols-outlined text-2xl flex-shrink-0"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                {isCritical ? 'gshield' : isSafe ? 'verified' : 'warning'}
              </span>
              <div className="flex-1">
                <div className="text-body-sm font-bold tracking-tight uppercase font-mono">
                  {n.title}
                </div>
                <div className="text-xs text-on-surface/90 mt-0.5">{n.message}</div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
