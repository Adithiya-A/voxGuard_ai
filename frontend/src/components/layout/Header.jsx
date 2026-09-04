import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

export default function Header() {
  const { user } = useApp();
  const location = useLocation();

  const getBreadcrumb = () => {
    const path = location.pathname;
    if (path.includes('live-call')) return 'Live Telemetry / Active Voice Stream (VS-2026-00081)';
    if (path.includes('investigation')) return 'Adversary Forensics / Deepfake Investigation Dossier';
    if (path.includes('incidents')) return 'Threat Response / Mitigations & Triage Queue';
    if (path.includes('call-history')) return 'Forensics Archive / Call Attestation History';
    if (path.includes('audit-logs')) return 'Immutable Ledger / SHA-256 Cryptographic Proof';
    if (path.includes('analytics')) return 'Model Telemetry / Benchmark Accuracy Metrics';
    if (path.includes('settings')) return 'SOC Policies / Risk Threshold & Weight Matrix';
    if (path.includes('demo')) return 'Adversary Emulation / Red-Team Attack Simulator';
    return 'SOC Command / Security Overview Dashboard';
  };

  return (
    <header className="sticky top-0 z-30 flex justify-between items-center w-full px-6 py-3 border-b border-outline-variant bg-surface-container-lowest/85 backdrop-blur-md shadow-sm">
      {/* Left Breadcrumb & Enclave pill */}
      <div className="flex items-center gap-6">
        <div>
          <div className="flex items-center gap-2 text-label-code-sm font-mono text-outline text-xs mb-0.5">
            <Link to="/dashboard" className="hover:text-primary-container transition-colors">
              Console
            </Link>
            <span>/</span>
            <span className="text-on-surface-variant font-medium">{getBreadcrumb()}</span>
          </div>
          <div className="text-body-sm font-semibold text-primary-fixed-dim flex items-center gap-2">
            <span>Enclave Alpha // Real-Time Voice Biometric Security</span>
          </div>
        </div>

        {/* Real-Time Defense Pill */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-surface-container border border-primary-container/30 rounded-full">
          <span className="w-2 h-2 rounded-full bg-primary-container animate-pulse"></span>
          <span className="text-label-code-sm font-mono text-primary-container font-semibold uppercase tracking-wider text-[11px]">
            ZERO-TRUST VOICE ATTESTATION
          </span>
        </div>
      </div>

      {/* Right Controls & Profile */}
      <div className="flex items-center gap-4">
        {/* Latency & Stream Telemetry */}
        <div className="hidden md:flex items-center gap-3 text-label-code-sm font-mono text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-low border border-outline-variant text-on-surface-variant">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-container"></span>
            <span>WebSocket Ingress: 14ms</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-low border border-outline-variant text-primary-fixed-dim">
            <span className="material-symbols-outlined text-xs">terminal</span>
            <span>STIX 2.1 Live</span>
          </div>
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-1 border-l border-outline-variant/60 pl-3">
          <Link
            to="/demo"
            className="px-2.5 py-1 rounded bg-primary-container/10 border border-primary-container/40 text-primary-container hover:bg-primary-container/20 text-xs font-mono font-semibold transition-all flex items-center gap-1"
            title="Launch Demo Attack Simulator"
          >
            <span className="material-symbols-outlined text-sm">sensors</span>
            <span>Demo Mode</span>
          </Link>
        </div>

        {/* Analyst Profile */}
        <div className="flex items-center gap-3 pl-3 border-l border-outline-variant/60">
          <div className="relative">
            <div className="w-8 h-8 rounded-full border border-primary-container/40 bg-surface-container-high flex items-center justify-center text-primary-container font-mono text-xs font-bold">
              CV
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-primary-container rounded-full ring-2 ring-surface-container-lowest"></span>
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-body-sm font-semibold text-on-surface leading-tight">{user.name}</div>
            <div className="text-label-code-sm font-mono text-outline text-[11px] leading-tight">
              {user.role}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
