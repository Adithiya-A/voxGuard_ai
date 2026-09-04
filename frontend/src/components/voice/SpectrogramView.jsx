import React, { useEffect, useRef } from 'react';

export default function SpectrogramView({ isLive = true, intensity = 87 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;
    let phase = 0;

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Background grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 24) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += 18) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Draw synthetic / vocal frequency bars
      const numBars = 48;
      const barWidth = w / numBars;
      for (let i = 0; i < numBars; i++) {
        // High intensity creates distinct jitter & synthetic harmonics
        const freqWave = Math.sin(phase + i * 0.25) * 0.5 + 0.5;
        const noise = (Math.random() * 0.3) * (intensity / 100);
        const barHeight = Math.max(6, (freqWave + noise) * (h * 0.75));

        const isSyntheticBand = i > 28 && intensity > 60;
        ctx.fillStyle = isSyntheticBand
          ? 'rgba(239, 68, 68, 0.75)'
          : i % 2 === 0
          ? 'rgba(0, 229, 255, 0.75)'
          : 'rgba(56, 189, 248, 0.6)';

        ctx.fillRect(i * barWidth + 1, h - barHeight, barWidth - 2, barHeight);

        // Mirror subtle reflections
        ctx.fillStyle = isSyntheticBand
          ? 'rgba(239, 68, 68, 0.15)'
          : 'rgba(0, 229, 255, 0.12)';
        ctx.fillRect(i * barWidth + 1, 0, barWidth - 2, barHeight * 0.2);
      }

      // Center waveform trace
      ctx.beginPath();
      ctx.strokeStyle = intensity > 60 ? '#ef4444' : '#00e5ff';
      ctx.lineWidth = 2;
      ctx.shadowBlur = 8;
      ctx.shadowColor = intensity > 60 ? 'rgba(239, 68, 68, 0.6)' : 'rgba(0, 229, 255, 0.6)';

      for (let x = 0; x < w; x += 4) {
        const y = h / 2 + Math.sin(x * 0.05 + phase * 2) * (h * 0.22) * (isLive ? 1 : 0.2);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      phase += isLive ? 0.08 : 0.01;
      animationId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [isLive, intensity]);

  return (
    <div className="relative w-full h-36 bg-surface-container-lowest rounded-xl border border-outline-variant/80 overflow-hidden shadow-inner">
      <canvas ref={canvasRef} width={500} height={144} className="w-full h-full block" />
      {/* Overlay status watermark */}
      <div className="absolute top-2 left-3 flex items-center gap-2 text-[10px] font-mono text-outline">
        <span className="w-1.5 h-1.5 rounded-full bg-primary-container animate-ping"></span>
        <span>MEL-SPECTROGRAM // 0–8kHz ACOUSTIC INGRESS</span>
      </div>
      {intensity > 60 && (
        <div className="absolute bottom-2 right-3 text-[10px] font-mono text-error font-bold bg-error-container/40 px-2 py-0.5 rounded border border-error/50">
          GLOTTAL PHASE ARTIFACT: 4.8kHz
        </div>
      )}
    </div>
  );
}
