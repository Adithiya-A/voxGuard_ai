/**
 * Firebase client config for cloud sync of calls/incidents (not live audio).
 * Live telemetry always uses WebSocket. Admin credentials never ship here.
 */
export function getFirebaseClientConfig() {
  const config = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
    appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
  };
  const configured = Boolean(config.apiKey && config.projectId);
  return {
    configured,
    config,
    status: configured ? 'CONFIGURED' : 'NOT_CONFIGURED',
    note: 'WebSocket remains the live audio/telemetry channel. Firebase is optional cloud sync.',
  };
}

export function subscribeCollection(_name, _onChange) {
  return () => {};
}
