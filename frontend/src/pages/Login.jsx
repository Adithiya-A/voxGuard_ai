import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useApp();
  const [analystId, setAnalystId] = useState('CV-8821');
  const [orgPin, setOrgPin] = useState('FIN-CORP-909');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const handleLogin = (e) => {
    e.preventDefault();
    setIsAuthenticating(true);
    setTimeout(() => {
      setUser({
        name: 'C. Vance, CISSP',
        role: 'Lead Incident Commander',
        badgeId: analystId,
        organization: 'FinSecure Global Core // Enclave Alpha',
        isAuthenticated: true,
      });
      navigate('/dashboard');
    }, 800);
  };

  return (
    <div className="min-h-screen w-screen bg-surface-container-lowest text-on-surface flex flex-col justify-between relative overflow-hidden bg-grid-cyber">
      {/* Background ambient gradient bursts */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary-container/5 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-96 h-96 bg-secondary/5 rounded-full blur-[120px] pointer-events-none" />

      {/* Top Header */}
      <header className="px-8 py-5 flex items-center justify-between border-b border-outline-variant/40 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-surface-container-high border border-primary-container/40 flex items-center justify-center text-primary-container shadow-[0_0_15px_rgba(0,229,255,0.25)]">
            <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              security
            </span>
          </div>
          <div>
            <span className="text-headline-sm font-bold tracking-tight text-primary-fixed-dim">VoxGuard AI</span>
            <span className="text-label-code-sm text-outline ml-2 font-mono text-xs">SOC ZERO-TRUST GATEWAY</span>
          </div>
        </div>

        <div className="flex items-center gap-3 text-label-code-sm font-mono text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="text-on-surface-variant">FIPS 140-3 Cryptographic HSM: ONLINE</span>
        </div>
      </header>

      {/* Center Auth Card */}
      <div className="flex-1 flex items-center justify-center p-6 z-10">
        <div className="w-full max-w-md bg-surface-container-low/85 backdrop-blur-2xl border border-outline-variant rounded-2xl p-8 shadow-[0_8px_32px_rgba(0,0,0,0.8)] relative">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary-container via-secondary to-primary-container"></div>

          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-surface-container border border-primary-container/30 mb-3 shadow-[0_0_20px_rgba(0,229,255,0.2)]">
              <span className="material-symbols-outlined text-primary-container text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                fingerprint
              </span>
            </div>
            <h1 className="text-headline-sm font-bold text-on-surface">SOC Operator Authentication</h1>
            <p className="text-body-sm text-outline mt-1 font-mono text-xs">
              Hardware-Attested WebAuthn &amp; Smart Card Biometric Gateway
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <label className="block text-label-code-sm font-mono text-outline uppercase text-xs">
                Analyst Call-Sign / ID
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={analystId}
                  onChange={(e) => setAnalystId(e.target.value)}
                  className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-3.5 py-2.5 text-body-sm text-on-surface focus:border-primary-container focus:outline-none font-mono"
                  required
                />
                <span className="material-symbols-outlined absolute right-3 top-2.5 text-outline text-lg">
                  badge
                </span>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-label-code-sm font-mono text-outline uppercase text-xs">
                Enclave Security Key / PIN
              </label>
              <div className="relative">
                <input
                  type="password"
                  value={orgPin}
                  onChange={(e) => setOrgPin(e.target.value)}
                  className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-3.5 py-2.5 text-body-sm text-on-surface focus:border-primary-container focus:outline-none font-mono"
                  required
                />
                <span className="material-symbols-outlined absolute right-3 top-2.5 text-outline text-lg">
                  key
                </span>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isAuthenticating}
                className="w-full py-3 rounded-lg bg-primary-container text-on-primary-fixed hover:bg-primary font-mono text-label-code-md font-bold tracking-wider transition-all shadow-[0_0_20px_rgba(0,229,255,0.35)] flex items-center justify-center gap-2 active:scale-98"
              >
                {isAuthenticating ? (
                  <>
                    <span className="w-4 h-4 border-2 border-on-primary-fixed border-t-transparent rounded-full animate-spin"></span>
                    <span>VERIFYING HARDWARE TOKEN...</span>
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-lg">lock_open</span>
                    <span>AUTHENTICATE &amp; ENTER SOC</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Quick Demo Bypass */}
          <div className="mt-5 pt-4 border-t border-outline-variant/60 text-center">
            <button
              onClick={() => navigate('/dashboard')}
              className="text-primary-fixed-dim hover:text-primary-container text-xs font-mono underline tracking-wide"
            >
              Skip to Console Dashboard (Hackathon Presentation Mode) &rarr;
            </button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="px-8 py-4 border-t border-outline-variant/40 text-center text-xs font-mono text-outline">
        VoxGuard AI &copy; 2026 Smart India Hackathon Prototype // Zero-Trust Acoustic Forensics
      </footer>
    </div>
  );
}
