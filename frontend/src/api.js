const API_BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

export const api = {
  dashboard: () => request('/api/dashboard'),
  agents: () => request('/api/agents'),
  anomalies: (params = {}) => request(`/api/anomalies?${new URLSearchParams(Object.entries(params).filter(([, value]) => value && value !== 'all'))}`),
  anomaly: (id) => request(`/api/anomalies/${id}`),
  graph: (id) => request(`/api/cascades${id ? `?anomaly_id=${id}` : ''}`),
  whatif: (anomalyId, actionId) => request(`/api/cascades/${anomalyId}/whatif/${actionId}`),
  explainCascade: async (anomalyId, onEvent) => {
    const response = await fetch(`${API_BASE}/api/cascades/${anomalyId}/explain`, { method: 'POST', headers: { Accept: 'text/event-stream' } })
    if (!response.ok || !response.body) throw new Error(`Explain failed (${response.status})`)
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n'); buffer = frames.pop() || ''
      frames.forEach((frame) => { const event = frame.match(/^event: (.+)$/m)?.[1]; const data = frame.match(/^data: (.+)$/m)?.[1]; if (event && data) onEvent(event, JSON.parse(data)) })
    }
  },
  reconciliation: () => request('/api/reconciliation'),
  documents: () => request('/api/documents'),
  alerts: () => request('/api/alerts'),
  outcomes: () => request('/api/outcomes'),
  system: () => request('/api/system'),
  escalations: () => request('/api/escalations'),
  injectIncident: () => request('/api/demo/inject', { method: 'POST' }),
  injectStorm: () => request('/api/demo/storm', { method: 'POST' }),
  resetDemo: () => request('/api/demo/reset', { method: 'POST' }),
  reportUrl: (anomalyId) => `${API_BASE}/api/anomalies/${anomalyId}/report`,
  scan: () => request('/api/scan', { method: 'POST' }),
  chat: (payload) => request('/api/chat', { method: 'POST', body: JSON.stringify(payload) }),
  chatStream: async (payload, onEvent) => {
    const response = await fetch(`${API_BASE}/api/chat/stream`, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(payload) })
    if (!response.ok || !response.body) throw new Error(`Chat stream failed (${response.status})`)
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n'); buffer = frames.pop() || ''
      frames.forEach((frame) => { const event = frame.match(/^event: (.+)$/m)?.[1]; const data = frame.match(/^data: (.+)$/m)?.[1]; if (event && data) onEvent(event, JSON.parse(data)) })
    }
  },
  applyAction: (anomalyId, actionId) => request(`/api/anomalies/${anomalyId}/actions/${actionId}/apply`, { method: 'POST' }),
  inspectDocument: (file) => { const form = new FormData(); form.append('file', file); return request('/api/documents/inspect', { method: 'POST', body: form }) },
}
