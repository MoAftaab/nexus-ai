export const WALT_ANIMATION_STATES = [
  'idle',
  'greeting',
  'listening',
  'thinking',
  'analysing',
  'walking-left',
  'walking-right',
  'dragging',
  'waiting',
  'speaking',
  'success',
  'warning',
  'error',
  'review',
  'sleeping',
  'waking',
]

export const CODEX_ATLAS_ROWS = {
  idle: { row: 0, frames: 6, fps: 6 },
  'running-right': { row: 1, frames: 8, fps: 8 },
  'running-left': { row: 2, frames: 8, fps: 8 },
  waving: { row: 3, frames: 4, fps: 6 },
  jumping: { row: 4, frames: 5, fps: 7 },
  failed: { row: 5, frames: 8, fps: 7 },
  waiting: { row: 6, frames: 6, fps: 6 },
  running: { row: 7, frames: 6, fps: 8 },
  review: { row: 8, frames: 6, fps: 6 },
}

const stateToAtlas = {
  idle: 'idle',
  greeting: 'waving',
  listening: 'waiting',
  thinking: 'review',
  analysing: 'review',
  'walking-left': 'running-left',
  'walking-right': 'running-right',
  dragging: 'running',
  waiting: 'waiting',
  speaking: 'waving',
  success: 'jumping',
  warning: 'waiting',
  error: 'failed',
  review: 'review',
  sleeping: 'idle',
  waking: 'waving',
}

export function getAtlasAnimation(state) {
  const atlasState = stateToAtlas[state] || 'idle'
  return { id: atlasState, ...CODEX_ATLAS_ROWS[atlasState] }
}

export function isReviewContext(page) {
  return ['documents', 'changes', 'archive'].includes(page)
}

function compactCurrency(value) {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'EUR',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Number(value) || 0)
}

export function buildWaltContextCards(dashboard, anomalies = []) {
  const open = anomalies.filter((item) => item.status !== 'resolved')
  const exposure = open.reduce((total, item) => total + (Number(item.impact) || 0), 0)
  const priority = open.filter((item) => ['critical', 'high'].includes(item.severity)).length
  const evidence = open.reduce((total, item) => total + (Array.isArray(item.evidence) ? item.evidence.length : 0), 0)
  const sources = new Set(open.flatMap((item) => {
    if (Array.isArray(item.systems)) return item.systems
    return String(item.system || '').split('·').map((system) => system.trim())
  }).filter(Boolean))
  const liveExposure = dashboard?.metrics?.find((metric) => /exposure/i.test(metric.label || metric.title || ''))?.value
  const exposureValue = typeof liveExposure === 'string' && /[^\d.,-]/.test(liveExposure)
    ? liveExposure
    : compactCurrency(liveExposure || exposure)

  return [
    { id: 'exposure', label: 'Exposure', value: exposureValue, tone: 'coral' },
    { id: 'priority', label: 'Priority', value: String(priority), tone: 'amber' },
    { id: 'evidence', label: 'Evidence', value: String(evidence), tone: 'blue' },
    { id: 'sources', label: 'Sources', value: String(sources.size), tone: 'green' },
  ]
}
