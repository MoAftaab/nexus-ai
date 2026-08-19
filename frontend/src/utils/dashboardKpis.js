const SEVERITY_META = [
  ['critical', 'Critical', '#DA0C1F'],
  ['high', 'High', '#E67364'],
  ['medium', 'Medium', '#FCCD22'],
  ['low', 'Low', '#64A844'],
]

const SYSTEM_COLORS = ['#008C82', '#8CBEE6', '#FAAA3C', '#C882BE', '#E67364', '#64A844']

export function buildSystemExposure(anomalies = []) {
  const systems = new Map()
  anomalies
    .filter((item) => item.status !== 'resolved')
    .forEach((item) => {
      const names = [...new Set(String(item.system || 'Unassigned')
        .split(/\s*(?:·|\/|,|\||→)\s*/)
        .map((name) => name.trim())
        .filter(Boolean))]
      const allocatedExposure = (Number(item.impact) || 0) / Math.max(names.length, 1)
      names.forEach((system) => {
        const current = systems.get(system) || { exposure: 0, findings: 0 }
        systems.set(system, {
          exposure: current.exposure + allocatedExposure,
          findings: current.findings + 1,
        })
      })
    })

  const ranked = [...systems.entries()]
    .map(([system, values]) => ({ system, ...values }))
    .sort((a, b) => b.exposure - a.exposure || b.findings - a.findings || a.system.localeCompare(b.system))
    .slice(0, SYSTEM_COLORS.length)
  const total = ranked.reduce((sum, item) => sum + item.exposure, 0)

  return ranked.map((item, index) => ({
    system: item.system,
    exposure: Math.round(item.exposure),
    findings: item.findings,
    share: total ? Math.round((item.exposure / total) * 100) : 0,
    color: SYSTEM_COLORS[index],
  }))
}

export function buildValueSignals(workflow = {}, anomalies = []) {
  const verifiedValue = Number(workflow?.verified_value_protected) || 0
  const awaitingValue = Number(workflow?.value_awaiting_approval) || 0
  const measurableValue = verifiedValue + awaitingValue
  const timeline = buildRiskTimeline(anomalies)
  const systems = buildSystemExposure(anomalies)
  const openFindings = anomalies.filter((item) => item.status !== 'resolved').length

  return {
    verifiedValue,
    awaitingValue,
    protectionRate: measurableValue ? Math.round((verifiedValue / measurableValue) * 100) : 0,
    nearestWindow: timeline[0]?.label || 'Clear',
    systemsAtRisk: systems.length,
    openFindings,
  }
}

export function buildExposureBySeverity(anomalies = []) {
  const open = anomalies.filter((item) => item.status !== 'resolved')
  return SEVERITY_META.map(([key, severity, color]) => {
    const matching = open.filter((item) => String(item.severity).toLowerCase() === key)
    return {
      severity,
      exposure: matching.reduce((total, item) => total + (Number(item.impact) || 0), 0),
      findings: matching.length,
      color,
    }
  }).filter((item) => item.findings > 0)
}

export function minutesToImpact(value) {
  const text = String(value || '').trim().toLowerCase()
  const days = Number(text.match(/([\d.]+)\s*d/)?.[1] || 0)
  const hours = Number(text.match(/([\d.]+)\s*h/)?.[1] || 0)
  const minutes = Number(text.match(/([\d.]+)\s*m/)?.[1] || 0)
  const total = (days * 24 * 60) + (hours * 60) + minutes
  return Number.isFinite(total) && total > 0 ? total : Number.MAX_SAFE_INTEGER
}

export function buildRiskTimeline(anomalies = []) {
  return anomalies
    .filter((item) => item.status !== 'resolved')
    .map((item) => ({
      id: item.id,
      label: item.time_to_impact || 'Unscheduled',
      minutes: minutesToImpact(item.time_to_impact),
      exposure: Number(item.impact) || 0,
      title: item.title,
    }))
    .sort((a, b) => a.minutes - b.minutes)
    .slice(0, 7)
}

const PIPELINE_META = [
  ['awaiting_lead', 'Lead'],
  ['awaiting_manager', 'Manager'],
  ['awaiting_quality_compliance', 'Quality'],
  ['awaiting_director', 'Director'],
  ['verified', 'Verified'],
]

export function buildApprovalPipeline(workflow = {}) {
  const counts = workflow?.stage_counts || {}
  return PIPELINE_META
    .map(([key, stage]) => ({ stage, requests: Number(counts[key]) || 0 }))
    .filter((item) => item.requests > 0)
}

export function buildExecutiveMetrics(dashboard = {}, anomalies = []) {
  const open = anomalies.filter((item) => item.status !== 'resolved')
  const resolved = anomalies.length - open.length
  const critical = open.filter((item) => item.severity === 'critical').length
  const high = open.filter((item) => item.severity === 'high').length
  const exposure = dashboard?.metrics?.find((item) => item.label === 'Exposure at risk')?.value || 0
  const readiness = dashboard?.metrics?.find((item) => item.label === 'Readiness index')?.value || 0
  const containment = anomalies.length ? Math.round((resolved / anomalies.length) * 100) : 100
  return [
    { label: 'Exposure at risk', value: exposure, format: 'currency', trend: `${open.length} open findings`, tone: 'critical', detail: 'Live financial exposure' },
    { label: 'Critical interventions', value: critical + high, format: 'number', trend: `${critical} critical · ${high} high`, tone: critical ? 'critical' : 'watch', detail: 'Immediate action load' },
    { label: 'Line readiness', value: readiness, format: 'percent', trend: 'Severity-weighted score', tone: readiness >= 85 ? 'good' : 'watch', detail: 'Current operating posture' },
    { label: 'Containment rate', value: containment, format: 'percent', trend: `${resolved} of ${anomalies.length} findings resolved`, tone: 'good', detail: 'Verified controls only' },
  ]
}

export function buildDecisionFocus(anomalies = [], workflow = {}) {
  const open = anomalies
    .filter((item) => item.status !== 'resolved')
    .map((item) => ({ ...item, impactMinutes: minutesToImpact(item.time_to_impact) }))
    .sort((a, b) => a.impactMinutes - b.impactMinutes || (Number(b.impact) || 0) - (Number(a.impact) || 0))
  const anomaly = open[0] || null
  return {
    anomaly,
    action: anomaly?.actions?.[0] || null,
    awaitingDecision: Number(workflow?.awaiting_my_decision) || 0,
    awaitingValue: Number(workflow?.value_awaiting_approval) || 0,
    protectedValue: Number(workflow?.verified_value_protected) || 0,
  }
}

export function buildInterventionSnapshot(workflow = {}, outcomes = {}, anomalies = []) {
  const open = anomalies.filter((item) => item.status !== 'resolved')
  const protectedValue = Number(workflow?.verified_value_protected ?? outcomes?.summary?.value_protected) || 0
  const openExposure = open.reduce((total, item) => total + (Number(item.impact) || 0), 0)
  const trackedValue = protectedValue + openExposure
  return {
    protectedValue,
    openExposure,
    resolved: Number(outcomes?.summary?.anomalies_resolved) || anomalies.filter((item) => item.status === 'resolved').length,
    active: open.length,
    protectionRate: trackedValue ? Math.round((protectedValue / trackedValue) * 100) : 0,
  }
}

export function buildDataTrust(dashboard = {}, anomalies = []) {
  const open = anomalies.filter((item) => item.status !== 'resolved')
  const evidenceAttached = open.filter((item) => Array.isArray(item.evidence) && item.evidence.length > 0).length
  const confidenceValues = open.map((item) => Number(item.confidence)).filter((value) => Number.isFinite(value))
  const averageConfidence = confidenceValues.length
    ? Math.round(confidenceValues.reduce((total, value) => total + value, 0) / confidenceValues.length)
    : 0
  const modelF1 = Number(dashboard?.ml_model?.f1)
  return {
    records: Number(dashboard?.dataset?.records) || 0,
    scanCount: Number(dashboard?.scan_count) || 0,
    lastScan: dashboard?.last_scan || null,
    evidenceAttached,
    findingCount: open.length,
    averageConfidence,
    modelF1: Number.isFinite(modelF1) ? Math.round(modelF1 * 100) : null,
  }
}
