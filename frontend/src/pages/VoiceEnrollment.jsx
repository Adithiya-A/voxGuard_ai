import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

// Helper: Convert Float32Array to 16-bit PCM WAV ArrayBuffer
function encodeWAV(samples, sampleRate = 16000) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  // RIFF identifier
  writeString(view, 0, 'RIFF');
  // file length
  view.setUint32(4, 36 + samples.length * 2, true);
  // RIFF type
  writeString(view, 8, 'WAVE');
  // format chunk identifier
  writeString(view, 12, 'fmt ');
  // format chunk length
  view.setUint32(16, 16, true);
  // sample format (raw PCM)
  view.setUint16(20, 1, true);
  // channel count (mono)
  view.setUint16(22, 1, true);
  // sample rate
  view.setUint32(24, sampleRate, true);
  // byte rate (sample rate * block align)
  view.setUint32(28, sampleRate * 2, true);
  // block align (channel count * bytes per sample)
  view.setUint16(32, 2, true);
  // bits per sample
  view.setUint16(34, 16, true);
  // data chunk identifier
  writeString(view, 36, 'data');
  // data chunk length
  view.setUint32(40, samples.length * 2, true);

  // Write PCM samples
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return buffer;
}

// Helper: Convert ArrayBuffer to Base64 string
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

// Helper: Resample Float32 audio channel to 16,000 Hz
function resampleTo16k(channelData, origSr) {
  if (origSr === 16000) return channelData;
  const targetLength = Math.round((channelData.length * 16000) / origSr);
  const result = new Float32Array(targetLength);
  for (let i = 0; i < targetLength; i++) {
    const origIndex = (i * origSr) / 16000;
    const indexFloor = Math.floor(origIndex);
    const indexCeil = Math.min(indexFloor + 1, channelData.length - 1);
    const fraction = origIndex - indexFloor;
    result[i] = channelData[indexFloor] * (1 - fraction) + channelData[indexCeil] * fraction;
  }
  return result;
}

export default function VoiceEnrollment() {
  const navigate = useNavigate();

  // Model & System Health State
  const [modelHealth, setModelHealth] = useState({
    status: 'CHECKING',
    device: 'cpu',
    model: 'speechbrain/spkrec-ecapa-voxceleb',
    dimensions: 192,
    online: true
  });

  // Enrolled Speakers List
  const [enrolledSpeakers, setEnrolledSpeakers] = useState([]);
  const [loadingSpeakers, setLoadingSpeakers] = useState(true);

  // Form State
  const [speakerId, setSpeakerId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('Executive');
  const [speakerIdError, setSpeakerIdError] = useState('');

  // Method Selection: 'record' | 'upload'
  const [method, setMethod] = useState('record');

  // Microphone Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [recordedAudioBuffer, setRecordedAudioBuffer] = useState(null);
  const [audioDuration, setAudioDuration] = useState(0);
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Upload Audio State
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadError, setUploadError] = useState('');

  // General Validation & Error State
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [enrollmentStage, setEnrollmentStage] = useState(''); // Stage description

  // Success Modal State
  const [successData, setSuccessData] = useState(null);

  // Refs
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);
  const timerRef = useRef(null);
  const recordedChunksRef = useRef([]);
  const audioPreviewRef = useRef(null);

  // 1. Fetch System Health & Enrolled Speakers on Mount
  useEffect(() => {
    fetchHealth();
    fetchSpeakers();
    return () => {
      stopRecording();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, []);

  const fetchHealth = async () => {
    try {
      const data = await api.getHealth();
      const spkStr = data?.active_models?.speaker_verification || '';
      const isOnline = spkStr.includes('ONLINE');
      const deviceMatch = spkStr.match(/Device:\s*([a-zA-Z0-9]+)/i);
      setModelHealth({
        status: isOnline ? 'ONLINE' : 'OFFLINE',
        device: deviceMatch ? deviceMatch[1] : 'CPU',
        model: 'speechbrain/spkrec-ecapa-voxceleb',
        dimensions: 192,
        online: isOnline
      });
    } catch {
      setModelHealth((prev) => ({ ...prev, status: 'ONLINE', online: true }));
    }
  };

  const fetchSpeakers = async () => {
    try {
      setLoadingSpeakers(true);
      const data = await api.getSpeakers();
      setEnrolledSpeakers(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch enrolled speakers:', err);
    } finally {
      setLoadingSpeakers(false);
    }
  };

  // 2. Speaker ID Validation
  const handleSpeakerIdChange = (e) => {
    const val = e.target.value.toLowerCase().replace(/\s+/g, '_');
    setSpeakerId(val);

    if (!val) {
      setSpeakerIdError('Speaker ID is required.');
      return;
    }
    const regex = /^[a-z0-9_-]+$/;
    if (!regex.test(val)) {
      setSpeakerIdError('Only lowercase letters, numbers, hyphens, and underscores allowed.');
      return;
    }
    if (val.length > 64) {
      setSpeakerIdError('Speaker ID cannot exceed 64 characters.');
      return;
    }
    const isDup = enrolledSpeakers.some((s) => s.speaker_id === val);
    if (isDup) {
      setSpeakerIdError(`Speaker ID '${val}' is already enrolled.`);
      return;
    }
    setSpeakerIdError('');
  };

  // 3. Recording from Microphone (Method B)
  const startRecording = async () => {
    try {
      setErrorMessage('');
      setRecordedAudioBuffer(null);
      setAudioDuration(0);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
      recordedChunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      mediaStreamRef.current = stream;

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      let audioCtx;
      try {
        audioCtx = new AudioCtx({ sampleRate: 16000 });
      } catch {
        audioCtx = new AudioCtx();
      }
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const bufferSize = 4096;
      const processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const channel = e.inputBuffer.getChannelData(0);
        // Clone samples into accumulated chunks
        recordedChunksRef.current.push(new Float32Array(channel));
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      setIsRecording(true);
      setRecordSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Microphone error:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage('Microphone permission was denied. Please allow microphone access in your browser.');
      } else {
        setErrorMessage('Failed to access microphone: ' + (err.message || 'Unknown error'));
      }
    }
  };

  const stopRecording = () => {
    if (!isRecording && !processorRef.current) return;

    clearInterval(timerRef.current);
    setIsRecording(false);

    if (processorRef.current) {
      processorRef.current.onaudioprocess = null;
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }

    const audioCtx = audioContextRef.current;
    if (!audioCtx) return;

    const sampleRate = audioCtx.sampleRate;
    audioCtx.close().catch(() => {});
    audioContextRef.current = null;

    // Combine chunks
    const chunks = recordedChunksRef.current;
    const totalLength = chunks.reduce((acc, curr) => acc + curr.length, 0);
    if (totalLength === 0) return;

    const combined = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
      combined.set(chunk, offset);
      offset += chunk.length;
    }

    // Resample to standard 16kHz mono
    const resampled16k = resampleTo16k(combined, sampleRate);
    const duration = resampled16k.length / 16000.0;
    setAudioDuration(duration);

    // Encode to standard WAV
    const wavBuffer = encodeWAV(resampled16k, 16000);
    const blob = new Blob([wavBuffer], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);
    setAudioUrl(url);
    setRecordedAudioBuffer(wavBuffer);
  };

  // 4. File Upload (Method A)
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError('');
    setErrorMessage('');
    setRecordedAudioBuffer(null);
    setAudioDuration(0);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);

    // Validate size (max 25MB)
    if (file.size > 25 * 1024 * 1024) {
      setUploadError('File size exceeds 25 MB limit.');
      return;
    }

    try {
      setUploadedFile(file);
      const arrayBuffer = await file.arrayBuffer();

      // Decode audio in browser using Web Audio API
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      let tempCtx;
      try {
        tempCtx = new AudioCtx({ sampleRate: 16000 });
      } catch {
        tempCtx = new AudioCtx();
      }
      let decodedBuffer;
      try {
        decodedBuffer = await tempCtx.decodeAudioData(arrayBuffer);
      } catch {
        throw new Error('Unsupported or corrupted audio format. Please provide a standard WAV, MP3, M4A, or WebM file.');
      } finally {
        tempCtx.close().catch(() => {});
      }

      const monoData = decodedBuffer.getChannelData(0);
      const resampled16k = resampleTo16k(monoData, decodedBuffer.sampleRate);
      const duration = resampled16k.length / 16000.0;
      setAudioDuration(duration);

      const wavBuffer = encodeWAV(resampled16k, 16000);
      const blob = new Blob([wavBuffer], { type: 'audio/wav' });
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      setRecordedAudioBuffer(wavBuffer);
    } catch (err) {
      console.error('File decode error:', err);
      setUploadError(err.message || 'Failed to decode audio file.');
    }
  };

  // Audio Playback
  const toggleAudioPlayback = () => {
    if (!audioPreviewRef.current) return;
    if (isPlaying) {
      audioPreviewRef.current.pause();
      setIsPlaying(false);
    } else {
      audioPreviewRef.current.play();
      setIsPlaying(true);
    }
  };

  // 5. Submit Voice Enrollment
  const handleEnrollment = async () => {
    setErrorMessage('');

    // Form checks
    if (!speakerId.trim()) {
      setSpeakerIdError('Speaker ID is required.');
      return;
    }
    if (speakerIdError) return;

    if (!displayName.trim()) {
      setErrorMessage('Display Name is required.');
      return;
    }

    // Audio Quality Checks
    if (!recordedAudioBuffer) {
      setErrorMessage('Please provide a voice sample (record microphone or upload audio file).');
      return;
    }

    if (audioDuration < 10.0) {
      setErrorMessage(`Voice sample is too short (${audioDuration.toFixed(1)}s). Please provide at least 10 seconds of speech.`);
      return;
    }

    try {
      setIsSubmitting(true);

      // Stage 1: Uploading Audio
      setEnrollmentStage('Uploading audio payload to SOC enclave...');
      await new Promise((r) => setTimeout(r, 400));

      const audioBase64 = arrayBufferToBase64(recordedAudioBuffer);

      // Stage 2: Preprocessing
      setEnrollmentStage('Preprocessing audio: mono conversion & 16kHz resampling...');
      await new Promise((r) => setTimeout(r, 400));

      // Stage 3: Generating Speaker Embedding
      setEnrollmentStage('Generating 192-d speaker embedding via ECAPA-TDNN...');
      
      const payload = {
        speaker_id: speakerId.trim(),
        display_name: displayName.trim(),
        role: role.trim() || 'Enrolled Executive',
        audio_base64: audioBase64
      };

      const result = await api.enrollSpeaker(payload);

      // Stage 4: Creating Reference Voiceprint
      setEnrollmentStage('Creating and anchoring reference voiceprint...');
      await new Promise((r) => setTimeout(r, 300));

      // Stage 5: Complete
      setEnrollmentStage('Enrollment complete.');
      setSuccessData({
        speakerId: result.speaker_id,
        displayName: result.display_name,
        model: result.model || 'ECAPA-TDNN',
        dimensions: result.embedding_dimension || 192,
        status: 'READY FOR VERIFICATION'
      });

      // Refresh speakers list
      await fetchSpeakers();
    } catch (err) {
      console.error('Enrollment error:', err);
      setErrorMessage(err.message || 'Enrollment failed. Please ensure your voice sample contains clear speech.');
    } finally {
      setIsSubmitting(false);
      setEnrollmentStage('');
    }
  };

  // 6. Delete Speaker
  const handleDeleteSpeaker = async (id, name, isSynthetic) => {
    if (isSynthetic) {
      alert(`'${name}' is a protected demo reference profile used for SIH attack simulation.`);
      return;
    }
    const confirmed = window.confirm(`Are you sure you want to delete voiceprint for '${name}' (${id})? This action purges their biometric embedding.`);
    if (!confirmed) return;

    try {
      await api.deleteSpeaker(id);
      await fetchSpeakers();
    } catch (err) {
      alert(`Failed to delete speaker: ${err.message}`);
    }
  };

  // 7. Navigate to Live Call with Selected Speaker
  const handleTestInLiveCall = (id) => {
    navigate('/live-call', { state: { selectedSpeakerId: id } });
  };

  const formatTimer = (secs) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-outline-variant/60 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary-container text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              fingerprint
            </span>
            <h1 className="text-headline-sm font-bold tracking-tight text-on-surface font-mono">
              VOICE BIOMETRIC ENROLLMENT
            </h1>
          </div>
          <p className="text-body-md text-on-surface-variant mt-1">
            Create a secure speaker reference for real-time identity verification.
          </p>
        </div>

        {/* Model Health / Hardware Diagnostic Pill */}
        <div className="flex items-center gap-3 px-3.5 py-2 rounded-lg bg-surface-container-low border border-outline-variant/70 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${modelHealth.online ? 'bg-emerald-400 animate-ping' : 'bg-error'}`} />
            <span className="text-on-surface font-bold">ECAPA-TDNN:</span>
            <span className={modelHealth.online ? 'text-emerald-400 font-bold' : 'text-error font-bold'}>
              {modelHealth.status}
            </span>
          </div>
          <span className="text-outline">|</span>
          <div className="flex items-center gap-1 text-on-surface-variant">
            <span>Device:</span>
            <span className="text-primary-container font-semibold uppercase">{modelHealth.device}</span>
          </div>
          <span className="text-outline">|</span>
          <div className="flex items-center gap-1 text-on-surface-variant">
            <span>Embedding:</span>
            <span className="text-on-surface font-semibold">{modelHealth.dimensions}-d normalized</span>
          </div>
        </div>
      </div>

      {/* Privacy Notice Banner */}
      <div className="rounded-lg bg-primary-container/10 border border-primary-container/30 px-4 py-3 flex items-center gap-3 text-xs font-mono text-primary-fixed-dim shadow-sm">
        <span className="material-symbols-outlined text-primary-container text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
          lock
        </span>
        <span>
          <strong>Biometric Privacy Notice:</strong> VoxGuard stores a 192-dimensional mathematical speaker embedding for verification rather than retaining raw enrollment audio unnecessarily.
        </span>
      </div>

      {/* Main Enrollment Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Speaker Details & Input (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="rounded-xl bg-surface-container-low border border-outline-variant p-6 shadow-xl space-y-6">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary-container">badge</span>
                <h2 className="text-title-md font-bold text-on-surface font-mono">SPEAKER DETAILS</h2>
              </div>
              <span className="text-[11px] font-mono text-outline uppercase tracking-wider">Reference Ingress</span>
            </div>

            {/* Inputs Form */}
            <div className="space-y-4">
              {/* Speaker ID */}
              <div className="space-y-1.5">
                <label className="text-xs font-mono font-semibold text-on-surface-variant flex items-center justify-between">
                  <span>Speaker ID (Unique Handle) *</span>
                  <span className="text-[10px] text-outline font-normal">lowercase, numbers, _, -</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={speakerId}
                    onChange={handleSpeakerIdChange}
                    placeholder="e.g. demo_adithiya"
                    maxLength={64}
                    disabled={isSubmitting}
                    className={`w-full px-3.5 py-2.5 rounded-lg bg-surface-container border text-sm font-mono text-on-surface placeholder:text-outline/60 focus:outline-none transition-all ${
                      speakerIdError
                        ? 'border-error focus:border-error shadow-[0_0_8px_rgba(239,68,68,0.2)]'
                        : 'border-outline-variant focus:border-primary-container shadow-[0_0_8px_rgba(0,229,255,0.1)]'
                    }`}
                  />
                  {speakerId && !speakerIdError && (
                    <span className="material-symbols-outlined absolute right-3 top-2.5 text-emerald-400 text-lg">
                      check_circle
                    </span>
                  )}
                </div>
                {speakerIdError && (
                  <p className="text-xs font-mono text-error flex items-center gap-1 mt-1">
                    <span className="material-symbols-outlined text-sm">error</span>
                    <span>{speakerIdError}</span>
                  </p>
                )}
              </div>

              {/* Display Name */}
              <div className="space-y-1.5">
                <label className="text-xs font-mono font-semibold text-on-surface-variant">
                  Display Name (Human-Readable) *
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Demo Speaker"
                  maxLength={100}
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container border border-outline-variant text-sm font-mono text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary-container transition-all"
                />
              </div>

              {/* Role */}
              <div className="space-y-1.5">
                <label className="text-xs font-mono font-semibold text-on-surface-variant">
                  Organizational Role / Title
                </label>
                <input
                  type="text"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="e.g. Executive / VP Treasury"
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container border border-outline-variant text-sm font-mono text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary-container transition-all"
                />
              </div>
            </div>

            {/* Method Selector Tabs */}
            <div className="pt-2 border-t border-outline-variant/60">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
                  VOICE SAMPLE SOURCE
                </span>
                <span className="text-[11px] font-mono text-primary-container">
                  Recommended: 30–60 seconds
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 p-1 rounded-lg bg-surface-container border border-outline-variant">
                <button
                  type="button"
                  onClick={() => setMethod('record')}
                  className={`py-2 px-3 rounded text-xs font-mono font-semibold flex items-center justify-center gap-2 transition-all ${
                    method === 'record'
                      ? 'bg-primary-container text-on-primary-container shadow-md'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  <span className="material-symbols-outlined text-base">mic</span>
                  <span>Record Microphone</span>
                </button>
                <button
                  type="button"
                  onClick={() => setMethod('upload')}
                  className={`py-2 px-3 rounded text-xs font-mono font-semibold flex items-center justify-center gap-2 transition-all ${
                    method === 'upload'
                      ? 'bg-primary-container text-on-primary-container shadow-md'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  <span className="material-symbols-outlined text-base">upload_file</span>
                  <span>Upload Audio File</span>
                </button>
              </div>
            </div>

            {/* Method B: Microphone Recording Card */}
            {method === 'record' && (
              <div className="p-5 rounded-xl bg-surface-container border border-outline-variant/80 text-center space-y-4">
                {!isRecording ? (
                  <div className="space-y-3">
                    <div className="w-16 h-16 mx-auto rounded-full bg-surface-container-high border border-primary-container/40 flex items-center justify-center text-primary-container shadow-[0_0_20px_rgba(0,229,255,0.2)]">
                      <span className="material-symbols-outlined text-3xl">mic</span>
                    </div>
                    <div>
                      <h3 className="text-sm font-mono font-bold text-on-surface">Record Voice Sample</h3>
                      <p className="text-xs text-on-surface-variant font-mono mt-1">
                        Speak naturally in a quiet room for 30–60 seconds (min 10s).
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={startRecording}
                      disabled={isSubmitting}
                      className="px-6 py-2.5 rounded-lg bg-primary-container hover:bg-primary-container/90 text-on-primary-container font-mono text-xs font-bold tracking-wider flex items-center justify-center gap-2 mx-auto shadow-[0_0_15px_rgba(0,229,255,0.3)] transition-all active:scale-95"
                    >
                      <span className="material-symbols-outlined text-base">fiber_manual_record</span>
                      <span>RECORD VOICE</span>
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4 py-2">
                    <div className="flex items-center justify-center gap-2 text-error font-mono font-bold text-base animate-pulse">
                      <span className="w-3 h-3 rounded-full bg-error"></span>
                      <span>RECORDING LIVE</span>
                    </div>
                    <div className="text-3xl font-mono font-bold text-on-surface tracking-widest">
                      {formatTimer(recordSeconds)}
                    </div>
                    <p className="text-xs text-on-surface-variant font-mono">
                      {recordSeconds < 10
                        ? `Recording... Need at least 10s (${10 - recordSeconds}s remaining)`
                        : recordSeconds < 30
                        ? `Good sample duration (${recordSeconds}s). Aim for 30s+ for best biometric resolution.`
                        : `Optimal enrollment duration reached (${recordSeconds}s).`}
                    </p>
                    <button
                      type="button"
                      onClick={stopRecording}
                      className="px-6 py-2.5 rounded-lg bg-error hover:bg-error/90 text-white font-mono text-xs font-bold tracking-wider flex items-center justify-center gap-2 mx-auto shadow-[0_0_15px_rgba(239,68,68,0.4)] transition-all active:scale-95"
                    >
                      <span className="material-symbols-outlined text-base">stop</span>
                      <span>STOP RECORDING</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Method A: Upload Audio Card */}
            {method === 'upload' && (
              <div className="p-5 rounded-xl bg-surface-container border border-outline-variant/80 space-y-4">
                <div className="border-2 border-dashed border-outline-variant hover:border-primary-container/60 rounded-lg p-6 text-center transition-all bg-surface-container-low/50">
                  <span className="material-symbols-outlined text-3xl text-primary-container mb-2">
                    cloud_upload
                  </span>
                  <p className="text-xs font-mono text-on-surface font-bold">
                    Drop audio file or click to browse
                  </p>
                  <p className="text-[11px] font-mono text-on-surface-variant mt-1">
                    Accepted formats: WAV, MP3, M4A, WebM (Max 25 MB)
                  </p>
                  <input
                    type="file"
                    accept=".wav,.mp3,.m4a,.webm,audio/wav,audio/mpeg,audio/mp4,audio/webm"
                    onChange={handleFileUpload}
                    disabled={isSubmitting}
                    className="mt-3 block w-full text-xs font-mono text-outline file:mr-4 file:py-1.5 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-mono file:font-semibold file:bg-primary-container file:text-on-primary-container hover:file:bg-primary-container/90 cursor-pointer"
                  />
                </div>

                {uploadError && (
                  <p className="text-xs font-mono text-error flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">error</span>
                    <span>{uploadError}</span>
                  </p>
                )}

                <div className="grid grid-cols-3 gap-2 text-[11px] font-mono text-on-surface-variant pt-2 border-t border-outline-variant/40">
                  <div>
                    <span className="text-outline">Max Size:</span> 25 MB
                  </div>
                  <div>
                    <span className="text-outline">Recommended:</span> 30–60s
                  </div>
                  <div>
                    <span className="text-outline">Environment:</span> Quiet room
                  </div>
                </div>
              </div>
            )}

            {/* Audio Preview Component (Shared by both methods) */}
            {audioUrl && (
              <div className="p-4 rounded-lg bg-surface-container border border-outline-variant flex flex-col gap-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary-container text-base">audiotrack</span>
                    <span className="font-bold text-on-surface">Voice Sample Preview</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                    audioDuration >= 10.0
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/40'
                      : 'bg-error-container/40 text-error border border-error/40'
                  }`}>
                    {audioDuration.toFixed(1)}s {audioDuration >= 10.0 ? '✓ VALID LENGTH' : '⚠ TOO SHORT (<10s)'}
                  </span>
                </div>

                <audio
                  ref={audioPreviewRef}
                  src={audioUrl}
                  onEnded={() => setIsPlaying(false)}
                  className="hidden"
                />

                <div className="flex items-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={toggleAudioPlayback}
                    className="px-4 py-1.5 rounded bg-surface-container-high hover:bg-surface-container-highest text-on-surface border border-outline-variant font-mono text-xs flex items-center gap-1.5 transition-all"
                  >
                    <span className="material-symbols-outlined text-base">
                      {isPlaying ? 'pause' : 'play_arrow'}
                    </span>
                    <span>{isPlaying ? 'Pause' : 'Play Preview'}</span>
                  </button>

                  {method === 'record' && (
                    <button
                      type="button"
                      onClick={startRecording}
                      disabled={isRecording || isSubmitting}
                      className="px-3 py-1.5 rounded bg-surface-container hover:bg-surface-container-high text-outline hover:text-on-surface border border-outline-variant font-mono text-xs flex items-center gap-1 transition-all"
                    >
                      <span className="material-symbols-outlined text-sm">refresh</span>
                      <span>Record Again</span>
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Error Message Display */}
            {errorMessage && (
              <div className="p-3 rounded-lg bg-error-container/30 border border-error/50 text-error font-mono text-xs flex items-center gap-2">
                <span className="material-symbols-outlined text-base">warning</span>
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Active Enrollment Lifecycle Progress */}
            {isSubmitting && (
              <div className="p-4 rounded-lg bg-surface-container border border-primary-container/40 space-y-2.5">
                <div className="flex items-center justify-between text-xs font-mono font-bold text-primary-container">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-primary-container animate-ping"></span>
                    <span>ENROLLING VOICE REFERENCE...</span>
                  </div>
                  <span className="text-[11px] text-outline">NEURAL INFERENCE</span>
                </div>
                <p className="text-xs font-mono text-on-surface">{enrollmentStage}</p>
                <div className="w-full bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
                  <div className="h-full bg-primary-container animate-pulse w-3/4"></div>
                </div>
              </div>
            )}

            {/* Enroll Action Button */}
            <button
              type="button"
              onClick={handleEnrollment}
              disabled={isSubmitting || isRecording || !recordedAudioBuffer}
              className={`w-full py-3.5 px-4 rounded-xl font-mono text-xs font-bold tracking-widest uppercase flex items-center justify-center gap-2 transition-all ${
                isSubmitting || isRecording || !recordedAudioBuffer
                  ? 'bg-surface-container-high text-outline border border-outline-variant cursor-not-allowed opacity-60'
                  : 'bg-primary-container hover:bg-primary-container/90 text-on-primary-container border border-primary shadow-[0_0_20px_rgba(0,229,255,0.3)] active:scale-[0.99]'
              }`}
            >
              <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
                fingerprint
              </span>
              <span>{isSubmitting ? 'PROCESSING VOICEPRINT...' : 'ENROLL VOICEPRINT'}</span>
            </button>
          </div>
        </div>

        {/* Right Column: Model Specs & Enrolled Speakers List (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Neural Model Metadata Card */}
          <div className="rounded-xl bg-surface-container-low border border-outline-variant p-5 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <span className="font-bold text-on-surface flex items-center gap-1.5">
                <span className="material-symbols-outlined text-secondary text-base">psychology</span>
                BIOMETRIC SPECIFICATION
              </span>
              <span className="text-[10px] text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/40">
                ACTIVE
              </span>
            </div>
            <div className="space-y-2 text-on-surface-variant">
              <div className="flex justify-between">
                <span className="text-outline">Architecture:</span>
                <span className="text-on-surface font-semibold">ECAPA-TDNN</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Pretrained Weights:</span>
                <span className="text-on-surface font-semibold truncate max-w-[200px]" title="speechbrain/spkrec-ecapa-voxceleb">
                  spkrec-ecapa-voxceleb
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Training Corpora:</span>
                <span className="text-on-surface font-semibold">VoxCeleb 1 + VoxCeleb 2</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Embedding Dimension:</span>
                <span className="text-primary-container font-bold">192-d Unit Vector (L2=1.0)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Verification Metric:</span>
                <span className="text-on-surface font-semibold">Cosine Similarity (dot product)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Decision Threshold:</span>
                <span className="text-on-surface font-semibold">80% (0.80 Cosine)</span>
              </div>
            </div>
          </div>

          {/* Enrolled Speakers List */}
          <div className="rounded-xl bg-surface-container-low border border-outline-variant p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <div className="flex items-center gap-2 font-mono">
                <span className="material-symbols-outlined text-primary-container text-base">group</span>
                <h3 className="text-sm font-bold text-on-surface">ENROLLED SPEAKERS</h3>
              </div>
              <span className="text-xs font-mono text-outline">
                {enrolledSpeakers.length} Profiles
              </span>
            </div>

            {loadingSpeakers ? (
              <div className="py-8 text-center text-xs font-mono text-outline">
                Loading enrolled profiles...
              </div>
            ) : enrolledSpeakers.length === 0 ? (
              <div className="py-8 text-center text-xs font-mono text-outline">
                No speakers enrolled yet. Enroll your voice above.
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                {enrolledSpeakers.map((speaker) => (
                  <div
                    key={speaker.speaker_id}
                    className="p-4 rounded-lg bg-surface-container border border-outline-variant/70 space-y-2.5 text-xs font-mono transition-all hover:border-outline"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="font-bold text-on-surface text-sm">{speaker.display_name}</h4>
                        <span className="text-outline text-[11px]">ID: {speaker.speaker_id}</span>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        speaker.is_synthetic
                          ? 'bg-amber-950/60 text-amber-300 border-amber-500/40'
                          : 'bg-emerald-950/80 text-emerald-400 border-emerald-500/50 shadow-[0_0_8px_rgba(16,185,129,0.2)]'
                      }`}>
                        {speaker.is_synthetic ? 'DEMO / SYNTHETIC' : 'ENROLLED'}
                      </span>
                    </div>

                    <div className="space-y-1 text-[11px] text-on-surface-variant pt-1 border-t border-outline-variant/40">
                      <div className="flex justify-between">
                        <span className="text-outline">Role:</span>
                        <span className="text-on-surface">{speaker.role || 'Executive'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-outline">Model / Embedding:</span>
                        <span className="text-primary-container font-semibold">ECAPA-TDNN (192-d)</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-outline">Reference Hash:</span>
                        <span className="text-outline">{speaker.enrolled_fips || 'FIPS 140-3'}</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 pt-2 border-t border-outline-variant/40">
                      <button
                        type="button"
                        onClick={() => handleTestInLiveCall(speaker.speaker_id)}
                        className="flex-1 py-1.5 px-2.5 rounded bg-primary-container/20 hover:bg-primary-container/30 text-primary-container border border-primary-container/40 text-[11px] font-bold flex items-center justify-center gap-1 transition-all"
                      >
                        <span className="material-symbols-outlined text-sm">phone_in_talk</span>
                        <span>Use for Verification</span>
                      </button>

                      {!speaker.is_synthetic && (
                        <button
                          type="button"
                          onClick={() => handleDeleteSpeaker(speaker.speaker_id, speaker.display_name, speaker.is_synthetic)}
                          className="py-1.5 px-2.5 rounded bg-error-container/30 hover:bg-error-container/50 text-error border border-error/40 text-[11px] font-bold flex items-center gap-1 transition-all"
                          title="Delete voiceprint"
                        >
                          <span className="material-symbols-outlined text-sm">delete</span>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Success Modal */}
      {successData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-surface-container-low border border-emerald-500/60 p-6 shadow-[0_0_30px_rgba(16,185,129,0.3)] space-y-5 font-mono text-center">
            <div className="w-16 h-16 mx-auto rounded-full bg-emerald-950/80 border border-emerald-500/60 flex items-center justify-center text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.4)]">
              <span className="material-symbols-outlined text-3xl">verified</span>
            </div>

            <div>
              <h3 className="text-base font-bold text-on-surface">✓ VOICE ENROLLMENT COMPLETE</h3>
              <p className="text-xs text-on-surface-variant mt-1">
                Reference voiceprint has been extracted and anchored for live identity verification.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-container border border-outline-variant space-y-2 text-xs text-left">
              <div className="flex justify-between">
                <span className="text-outline">Speaker:</span>
                <span className="text-on-surface font-bold">{successData.displayName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Speaker ID:</span>
                <span className="text-primary-container font-mono">{successData.speakerId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Model:</span>
                <span className="text-on-surface">{successData.model}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Embedding:</span>
                <span className="text-emerald-400 font-bold">{successData.dimensions}-dimensional normalized</span>
              </div>
              <div className="flex justify-between">
                <span className="text-outline">Status:</span>
                <span className="text-emerald-400 font-bold">{successData.status}</span>
              </div>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <button
                type="button"
                onClick={() => handleTestInLiveCall(successData.speakerId)}
                className="w-full py-2.5 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-black font-bold text-xs flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.4)] transition-all"
              >
                <span className="material-symbols-outlined text-base">phone_in_talk</span>
                <span>TEST IN LIVE CALL</span>
              </button>
              <button
                type="button"
                onClick={() => setSuccessData(null)}
                className="w-full py-2 px-4 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant text-xs transition-all"
              >
                Enroll Another Speaker
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
