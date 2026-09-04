const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchApi(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });
    if (!res.ok) {
      throw new Error(`API error ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.warn(`API call to ${endpoint} failed, utilizing local fallback.`, err);
    throw err;
  }
}

export const api = {
  getHealth: () => fetchApi('/api/health'),
  getCalls: () => fetchApi('/api/calls'),
  getCallById: (id) => fetchApi(`/api/calls/${id}`),
  analyzeCall: (data) => fetchApi('/api/calls/analyze', { method: 'POST', body: JSON.stringify(data) }),
  getIncidents: () => fetchApi('/api/incidents'),
  getIncidentById: (id) => fetchApi(`/api/incidents/${id}`),
  incidentAction: (id, action, reason) => fetchApi(`/api/incidents/${id}/action`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
  }),
  getAnalytics: () => fetchApi('/api/analytics'),
  getAuditLogs: () => fetchApi('/api/audit-logs'),
  verifyEventHash: (id) => fetchApi(`/api/audit-logs/verify/${id}`),
  getSettings: () => fetchApi('/api/settings'),
  updateWeights: (weights) => fetchApi('/api/settings/weights', { method: 'POST', body: JSON.stringify(weights) }),
  getScenarios: () => fetchApi('/api/demo/scenarios'),
  getScenarioById: (id) => fetchApi(`/api/demo/scenario/${id}`),
};
