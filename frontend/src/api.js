const API_BASE = import.meta.env.VITE_API_URL || ''
const SESSION_KEY = 'nexusai.session'

export function session() {
  try { return JSON.parse(window.localStorage.getItem(SESSION_KEY) || 'null') } catch { return null }
}

export function clearSession() { window.localStorage.removeItem(SESSION_KEY) }

async function request(path, options = {}) {
  const stored = session()
  const auth = stored?.session_token ? { Authorization: `Bearer ${stored.session_token}` } : {}
  const response = await fetch(`${API_BASE}${path}`, {
    headers: options.body instanceof FormData ? { ...auth, ...options.headers } : { 'Content-Type': 'application/json', ...auth, ...options.headers },
    ...options,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

export const api = {
  signIn: (payload) => request('/api/auth/signin', { method: 'POST', body: JSON.stringify(payload) }),
  signOut: () => request('/api/auth/signout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  sites: () => request('/api/sites'),
  changes: (params = {}) => request(`/api/changes?${new URLSearchParams(Object.entries(params).filter(([, value]) => value))}`),
  change: (id) => request(`/api/changes/${id}`),
  changePreview: (payload) => request('/api/changes/preview', { method: 'POST', body: JSON.stringify(payload) }),
  createChange: (payload) => request('/api/changes', { method: 'POST', body: JSON.stringify(payload) }),
  submitChange: (id) => request(`/api/changes/${id}/submit`, { method: 'POST' }),
  reviseChange: (id) => request(`/api/changes/${id}/revise`, { method: 'POST' }),
  decideChange: (id, decision, comment) => { const route = { approved: 'approve', rejected: 'reject', returned: 'return' }[decision] || decision; return request(`/api/changes/${id}/${route}`, { method: 'POST', body: JSON.stringify({ comment }) }) },
  cancelChange: (id) => request(`/api/changes/${id}/cancel`, { method: 'POST' }),
  rollbackChange: (id, comment) => request(`/api/changes/${id}/rollback`, { method: 'POST', body: JSON.stringify({ comment }) }),
  changeDiff: (id) => request(`/api/changes/${id}/diff`),
  notifications: (unreadOnly = false) => request(`/api/notifications${unreadOnly ? '?unread_only=true' : ''}`),
  markNotificationRead: (id) => request(`/api/notifications/${id}/read`, { method: 'POST' }),
  inbox: () => request('/api/inbox'),
  workflowSummary: () => request('/api/workflow/summary'),
  adminUsers: () => request('/api/admin/users'),
  saveAdminUser: (payload) => request('/api/admin/users', { method: 'POST', body: JSON.stringify(payload) }),
  policy: () => request('/api/admin/policy'),
  savePolicy: (payload) => request('/api/admin/policy', { method: 'PUT', body: JSON.stringify(payload) }),
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
