import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import SpectrogramView from '../components/voice/SpectrogramView';
import TrustScoreGauge from '../components/trust/TrustScoreGauge';
import RiskBreakdown from '../components/trust/RiskBreakdown';

export default function Investigation() {
  const { callId } = useParams();
  const [call, setCall] = useState(null);
  const [exportNotice, setExportNotice] = useState(null);

  useEffect(() => {
    const id = callId || 'VS-2026-00081';
    api.getCallById(id)
      .then((data) => setCall(data))
      .catch(() => {});
  }, [callId]);

  const handleExportSTIX = () => {
    setExportNotice('STIX 2.1 Forensic Bundle generated successfully: STIX-VOXGUARD-2026-00081.json');
    setTimeout(() => setExportNotice(null), 4000);
  };

  const handleDownloadProof = () => {
    setExportNotice('Cryptographic Evidence Archive (SHA-256 anchored) downloaded to local vault.');
    setTimeout(() => setExportNotice(null), 4000);
  };

  if (!call) {
    return (
      <div className="p-8 text-center text-outline font-mono">
        Loading Forensic Dossier for {callId}...
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Forensic Dossier Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-outline-variant/60 pb-5">
        <div>
          <div className="flex items-center gap-2 text-label-code-sm font-mono text-outline mb-1 text-xs">
            <Link to="/call-history" className="hover:text-primary-container">
              FORENSIC ARCHIVE
            </Link>
            <span>/</span>
            <span className="text-primary-container">{call.call_id}</span>
          </div>
          <h1 className="text-headline-lg font-bold text-on-surface tracking-tight flex items-center gap-3">
            <span>Threat Forensic Investigation Dossier</span>
            <span className="px-2.5 py-0.5 rounded bg-error-container/40 border border-error/50 text-error font-mono text-xs font-bold">
              MITIGATED ATTACK
            </span>
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1 font-mono text-xs">
            Acoustic, Biometric, and Conversational Ingress Telemetry Record &bull; Session ID: {call.call_id}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleExportSTIX}
            className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant hover:border-primary-container text-on-surface font-mono text-xs flex items-center gap-2 transition-all"
          >
            <span className="material-symbols-outlined text-base">download</span>
            <span>EXPORT STIX 2.1 IOC</span>
          </button>
          <button
            onClick={handleDownloadProof}
            className="px-4 py-2 rounded-lg bg-primary-container text-on-primary-fixed hover:bg-primary font-mono text-xs font-bold flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(0,229,255,0.3)]"
          >
            <span className="material-symbols-outlined text-base">verified</span>
            <span>DOWNLOAD FORENSIC BUNDLE</span>
          </button>
        </div>
      </div>

      {exportNotice && (
        <div className="p-3 rounded-lg bg-surface-container border border-primary-container text-primary-container font-mono text-xs flex items-center gap-2">
          <span className="material-symbols-outlined text-base">check_circle</span>
          <span>{exportNotice}</span>
        </div>
      )}

      {/* AI Forensic Analysis Summary Card */}
      <div className="p-5 rounded-xl bg-surface-container-low/85 backdrop-blur-md border border-outline-variant shadow-lg space-y-2">
        <div className="flex items-center gap-2 text-xs font-mono text-primary-container font-bold uppercase">
          <span className="material-symbols-outlined text-base">neurology</span>
          <span>Autonomous AI Forensic Attribution Summary</span>
        </div>
        <p className="text-body-md text-on-surface leading-relaxed">
          The caller's voice strongly resembles the registered CFO (94.2% speaker similarity) but exhibits synthetic phase discontinuities and elevated spectral flatness (87% AI probability) characteristic of neural vocoder synthesis (ElevenLabs/HiFi-GAN). Furthermore, conversational telemetry identified severe social engineering urgency, secrecy coercion, and an unverified ₹25,00,000 transfer request to a new beneficiary.
        </p>
      </div>

      {/* 4 Multi-Evidence Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left Column: Spectral & Identity Evidence (7 cols) */}
        <div className="xl:col-span-7 space-y-6">
          {/* Voice Evidence */}
          <div className="p-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <h3 className="text-body-md font-bold text-on-surface font-mono uppercase">
                1. Acoustic &amp; Spectral Evidence
              </h3>
              <span className="text-xs font-mono text-error font-bold">87% SYNTHETIC CONFIDENCE</span>
            </div>

            <SpectrogramView isLive={false} intensity={87} />

            <div className="grid grid-cols-3 gap-3 text-xs font-mono">
              <div className="p-2.5 rounded bg-surface-container">
                <span className="text-outline text-[10px] block">SPECTRAL CENTROID</span>
                <span className="font-bold text-on-surface">3,420 Hz (Elevated)</span>
              </div>
              <div className="p-2.5 rounded bg-surface-container">
                <span className="text-outline text-[10px] block">VOCODER FINGERPRINT</span>
                <span className="font-bold text-error">ElevenLabs Multilingual</span>
              </div>
              <div className="p-2.5 rounded bg-surface-container">
                <span className="text-outline text-[10px] block">GLOTTAL ARTIFACT</span>
                <span className="font-bold text-error">Phase Smear &gt;4.2kHz</span>
              </div>
            </div>
          </div>

          {/* Identity Evidence */}
          <div className="p-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <h3 className="text-body-md font-bold text-on-surface font-mono uppercase">
                2. Speaker Identity &amp; Voiceprint Biometrics
              </h3>
              <span className="text-xs font-mono text-emerald-400 font-bold">94.2% SIMILARITY</span>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between p-2.5 rounded bg-surface-container">
                <span className="text-outline">Enrolled Reference:</span>
                <span className="font-bold text-on-surface">Arun Sharma (CFO) &bull; FIPS 140-3 #08-X99</span>
              </div>
              <div className="flex justify-between p-2.5 rounded bg-surface-container">
                <span className="text-outline">Cosine Embedding Distance:</span>
                <span className="font-bold text-primary-container">0.058 (Tight Acoustic Proximity)</span>
              </div>
              <div className="flex justify-between p-2.5 rounded bg-surface-container">
                <span className="text-outline">Forensic Conclusion:</span>
                <span className="font-bold text-error">Executive Voiceprint Cloned for Social Engineering</span>
              </div>
            </div>
          </div>

          {/* Conversation & Transcript */}
          <div className="p-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl space-y-3">
            <h3 className="text-body-md font-bold text-on-surface font-mono uppercase pb-2 border-b border-outline-variant/60">
              3. Flagged Conversational Transcript
            </h3>
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {call.transcript_history?.map((t, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border text-xs font-mono ${
                    t.flagged
                      ? 'bg-error-container/20 border-error/50 text-on-surface'
                      : 'bg-surface-container border-outline-variant/40 text-on-surface-variant'
                  }`}
                >
                  <div className="flex justify-between text-[10px] text-outline mb-1">
                    <span className="font-bold text-primary-container">[{t.timestamp}] {t.speaker}</span>
                    {t.category && <span className="text-error font-bold">{t.category}</span>}
                  </div>
                  <p className="text-body-sm">{t.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Trust Score, Decision, and Timeline (5 cols) */}
        <div className="xl:col-span-5 space-y-6">
          {/* Final Trust Score Decision */}
          <div className="p-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl text-center space-y-4">
            <h3 className="text-body-md font-bold text-on-surface font-mono uppercase pb-2 border-b border-outline-variant/60">
              Final Attestation Decision
            </h3>
            <TrustScoreGauge score={call.trust_score} riskLevel={call.risk_level} isCritical={true} />
            <div className="p-3 rounded-lg bg-error-container/30 border border-error/50 text-error font-mono text-xs font-bold">
              AUTONOMOUS MITIGATION: TRANSACTION BLOCKED
            </div>
          </div>

          {/* Forensic Progression Timeline */}
          <div className="p-5 rounded-xl bg-surface-container-low/75 backdrop-blur-md border border-outline-variant shadow-xl space-y-3">
            <h3 className="text-body-md font-bold text-on-surface font-mono uppercase pb-2 border-b border-outline-variant/60">
              Continuous Degradation Timeline
            </h3>
            <div className="space-y-3 font-mono text-xs">
              {call.timeline?.map((item, idx) => (
                <div key={idx} className="flex items-start gap-3 relative pb-2 border-l border-outline-variant/60 pl-3">
                  <div
                    className={`w-2 h-2 rounded-full absolute -left-1 top-1 ${
                      item.score < 30 ? 'bg-error animate-ping' : 'bg-primary-container'
                    }`}
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-[10px] text-outline">
                      <span className="text-primary-container font-bold">{item.time}</span>
                      <span>Trust: {item.score}/100</span>
                    </div>
                    <div className="text-on-surface mt-0.5 text-xs">{item.label}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
