import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

export default function Sidebar() {
  const { incidentsCount, activeCallId, triggerSecurityAction } = useApp();
  const navigate = useNavigate();

  const handleQuarantine = () => {
    triggerSecurityAction(activeCallId, 'BLOCK_TRANSACTION', 'Emergency operator quarantine triggered');
    navigate('/live-call');
  };

  const navItems = [
    { to: '/dashboard', label: 'Overview', icon: 'dashboard' },
    { to: '/live-call', label: 'Live Calls', icon: 'phone_in_talk', badge: 'LIVE', badgeType: 'live' },
    { to: '/incidents', label: 'Threats & Response', icon: 'gshield', badge: `${incidentsCount} ACTIVE`, badgeType: 'alert' },
    { to: '/demo', label: 'Attack Simulator', icon: 'sensors', badge: 'EMULATOR', badgeType: 'emulator' },
    { to: '/call-history', label: 'Call History', icon: 'history' },
    { to: '/audit-logs', label: 'Audit Logs', icon: 'verified_user' },
    { to: '/analytics', label: 'Analytics', icon: 'monitoring' },
    { to: '/settings', label: 'Settings', icon: 'settings' },
  ];

  return (
    <aside className="w-64 fixed h-screen docked left-0 top-0 flex flex-col justify-between border-r border-outline-variant bg-surface-container-lowest z-40 shadow-2xl">
      {/* Top Brand & Navigation */}
      <div className="flex flex-col">
        {/* Brand Header */}
        <div className="px-5 py-5 flex items-center gap-3 border-b border-outline-variant/60 bg-surface-container-lowest">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-lg bg-surface-container-high border border-primary-container/40 shadow-[0_0_15px_rgba(0,229,255,0.25)]">
            <span className="material-symbols-outlined text-primary-container text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              security
            </span>
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-primary-container animate-ping"></span>
          </div>
          <div className="flex flex-col">
            <span className="text-headline-sm font-semibold tracking-tight text-primary-fixed-dim">VoxGuard AI</span>
            <span className="text-label-code-sm text-on-surface-variant tracking-wider uppercase">Real-Time Voice Trust</span>
          </div>
        </div>

        {/* Section Label */}
        <div className="px-5 pt-4 pb-1">
          <span className="text-label-code-sm text-outline uppercase tracking-wider text-[11px] font-mono">
            OPERATIONS CONSOLE
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="mt-1 px-2 space-y-1 overflow-y-auto max-h-[calc(100vh-280px)]">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center justify-between px-4 py-2.5 rounded-r font-medium transition-all duration-150 text-body-md ${
                  isActive
                    ? 'text-primary-container bg-surface-container border-l-2 border-primary-container font-semibold shadow-[inset_0_0_12px_rgba(0,229,255,0.08)]'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <span
                  className="material-symbols-outlined text-xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </div>

              {/* Badges */}
              {item.badge && item.badgeType === 'live' && (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-surface-container border border-primary-container/40 text-primary-container font-mono text-[10px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-container animate-ping"></span>
                  {item.badge}
                </span>
              )}
              {item.badge && item.badgeType === 'alert' && (
                <span className="px-2 py-0.5 rounded-full bg-error-container/40 border border-error/50 text-error font-mono text-[10px] font-bold">
                  {item.badge}
                </span>
              )}
              {item.badge && item.badgeType === 'emulator' && (
                <span className="px-1.5 py-0.5 rounded bg-surface-container-highest border border-outline text-primary-fixed-dim font-mono text-[9px] font-bold">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Bottom Actions & Diagnostics */}
      <div className="p-4 border-t border-outline-variant bg-surface-container-lowest space-y-3">
        {/* Quarantine Threat Button */}
        <button
          onClick={handleQuarantine}
          className="w-full py-2.5 px-3 rounded-lg bg-error-container hover:bg-error-container/80 text-on-error-container border border-error/40 font-mono text-label-code-md font-bold tracking-wider flex items-center justify-center gap-2 shadow-[0_0_16px_rgba(239,68,68,0.25)] transition-all active:scale-[0.98]"
        >
          <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: "'FILL' 1" }}>
            block
          </span>
          <span>QUARANTINE THREAT</span>
        </button>

        {/* Telemetry Status Indicators */}
        <div className="space-y-1.5 pt-1 text-label-code-sm font-mono text-xs">
          <div className="flex items-center justify-between text-on-surface-variant px-2 py-1 rounded bg-surface-container-low border border-outline-variant/60">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-container animate-ping"></span>
              <span>Enclave Telemetry</span>
            </div>
            <span className="text-primary-container">14.2ms</span>
          </div>
          <div className="flex items-center justify-between text-on-surface-variant px-2 py-1">
            <span className="text-outline">STIX 2.1 Engine:</span>
            <span className="text-emerald-400 font-semibold">ONLINE</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
