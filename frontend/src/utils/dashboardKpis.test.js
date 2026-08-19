import test from 'node:test'
import assert from 'node:assert/strict'
import { buildApprovalPipeline, buildDataTrust, buildDecisionFocus, buildExecutiveMetrics, buildExposureBySeverity, buildInterventionSnapshot, buildRiskTimeline, buildSystemExposure, buildValueSignals } from './dashboardKpis.js'

test('exposure by severity is calculated from live anomaly values', () => {
  const anomalies = [
    { severity: 'critical', impact: 100, status: 'open' },
    { severity: 'critical', impact: 40, status: 'resolved' },
    { severity: 'high', impact: 25, status: 'open' },
    { severity: 'medium', impact: 10, status: 'open' },
  ]
  assert.deepEqual(buildExposureBySeverity(anomalies), [
    { severity: 'Critical', exposure: 100, findings: 1, color: '#DA0C1F' },
    { severity: 'High', exposure: 25, findings: 1, color: '#E67364' },
    { severity: 'Medium', exposure: 10, findings: 1, color: '#FCCD22' },
  ])
})

test('risk timeline parses each anomaly time-to-impact instead of using fixture points', () => {
  const anomalies = [
    { id: 'A', title: 'Later', impact: 500, time_to_impact: '4h', status: 'open' },
    { id: 'B', title: 'Sooner', impact: 200, time_to_impact: '30m', status: 'open' },
    { id: 'C', title: 'Closed', impact: 900, time_to_impact: '10m', status: 'resolved' },
  ]
  assert.deepEqual(buildRiskTimeline(anomalies), [
    { id: 'B', label: '30m', minutes: 30, exposure: 200, title: 'Sooner' },
    { id: 'A', label: '4h', minutes: 240, exposure: 500, title: 'Later' },
  ])
})

test('approval pipeline is derived from workflow stage counts', () => {
  const workflow = { stage_counts: { awaiting_lead: 2, awaiting_manager: 3, awaiting_director: 1, verified: 7 } }
  assert.deepEqual(buildApprovalPipeline(workflow), [
    { stage: 'Lead', requests: 2 },
    { stage: 'Manager', requests: 3 },
    { stage: 'Director', requests: 1 },
    { stage: 'Verified', requests: 7 },
  ])
})

test('executive KPIs calculate intervention load and containment from current data', () => {
  const dashboard = { metrics: [
    { label: 'Exposure at risk', value: 1_250_000 },
    { label: 'Readiness index', value: 82 },
  ] }
  const anomalies = [
    { severity: 'critical', status: 'open' },
    { severity: 'high', status: 'open' },
    { severity: 'medium', status: 'resolved' },
    { severity: 'low', status: 'resolved' },
  ]
  assert.deepEqual(buildExecutiveMetrics(dashboard, anomalies), [
    { label: 'Exposure at risk', value: 1_250_000, format: 'currency', trend: '2 open findings', tone: 'critical', detail: 'Live financial exposure' },
    { label: 'Critical interventions', value: 2, format: 'number', trend: '1 critical · 1 high', tone: 'critical', detail: 'Immediate action load' },
    { label: 'Line readiness', value: 82, format: 'percent', trend: 'Severity-weighted score', tone: 'watch', detail: 'Current operating posture' },
    { label: 'Containment rate', value: 50, format: 'percent', trend: '2 of 4 findings resolved', tone: 'good', detail: 'Verified controls only' },
  ])
})

test('system exposure is allocated from live open anomalies without double counting shared impact', () => {
  const anomalies = [
    { system: 'WMS · ERP', impact: 600, status: 'open' },
    { system: 'WMS / TMS', impact: 300, status: 'open' },
    { system: 'ERP', impact: 900, status: 'resolved' },
  ]
  assert.deepEqual(buildSystemExposure(anomalies), [
    { system: 'WMS', exposure: 450, findings: 2, share: 50, color: '#008C82' },
    { system: 'ERP', exposure: 300, findings: 1, share: 33, color: '#8CBEE6' },
    { system: 'TMS', exposure: 150, findings: 1, share: 17, color: '#FAAA3C' },
  ])
})

test('value signals combine approval value and live risk timing without fixtures', () => {
  const workflow = { value_awaiting_approval: 250, verified_value_protected: 750 }
  const anomalies = [
    { id: 'A', system: 'WMS · ERP', impact: 600, time_to_impact: '4h', status: 'open' },
    { id: 'B', system: 'TMS', impact: 300, time_to_impact: '45m', status: 'open' },
    { id: 'C', system: 'QMS', impact: 900, time_to_impact: '10m', status: 'resolved' },
  ]
  assert.deepEqual(buildValueSignals(workflow, anomalies), {
    verifiedValue: 750,
    awaitingValue: 250,
    protectionRate: 75,
    nearestWindow: '45m',
    systemsAtRisk: 3,
    openFindings: 2,
  })
})

test('decision focus selects the nearest open finding and its live control', () => {
  const focus = buildDecisionFocus([
    { id: 'LATER', impact: 900, time_to_impact: '4h', status: 'open', actions: [{ title: 'Later control' }] },
    { id: 'SOONER', impact: 200, time_to_impact: '20m', status: 'open', actions: [{ title: 'Protect dispatch' }] },
  ], { awaiting_my_decision: 2, value_awaiting_approval: 500, verified_value_protected: 800 })
  assert.equal(focus.anomaly.id, 'SOONER')
  assert.equal(focus.action.title, 'Protect dispatch')
  assert.equal(focus.awaitingValue, 500)
  assert.equal(focus.protectedValue, 800)
})

test('intervention snapshot distinguishes verified outcomes from live exposure', () => {
  assert.deepEqual(buildInterventionSnapshot(
    { verified_value_protected: 600 },
    { summary: { anomalies_resolved: 2 } },
    [{ impact: 400, status: 'open' }, { impact: 100, status: 'resolved' }],
  ), { protectedValue: 600, openExposure: 400, resolved: 2, active: 1, protectionRate: 60 })
})

test('data trust signals use live scan, evidence, and detector metadata', () => {
  const trust = buildDataTrust({
    scan_count: 17,
    last_scan: '2026-08-20T10:00:00Z',
    dataset: { records: 72900 },
    ml_model: { f1: 0.91 },
  }, [
    { status: 'open', confidence: 94, evidence: [{ label: 'Source', value: 'WMS' }] },
    { status: 'open', confidence: 86, evidence: [] },
    { status: 'resolved', confidence: 99, evidence: [{ label: 'Source', value: 'ERP' }] },
  ])
  assert.deepEqual(trust, { records: 72900, scanCount: 17, lastScan: '2026-08-20T10:00:00Z', evidenceAttached: 1, findingCount: 2, averageConfidence: 90, modelF1: 91 })
})
