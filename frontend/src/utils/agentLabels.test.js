import assert from 'node:assert/strict'
import test from 'node:test'
import { agentDisplayName, agentPresentation } from './agentLabels.js'

test('technical specialist names are presented in official hackathon agent names', () => {
  assert.equal(agentDisplayName('Sentinel'), 'Anomaly Agent')
  assert.equal(agentDisplayName('Correlator'), 'Correlation / Root-Cause Agent')
  assert.equal(agentDisplayName('Cascade'), 'Data-Quality Agent')
  assert.equal(agentDisplayName('Fix'), 'Action / Remediation Agent')
  assert.equal(agentDisplayName('Ingestion Agent'), 'Ingestion Agent')
  assert.equal(agentDisplayName('Impact Agent'), 'Impact Agent')
  assert.equal(agentDisplayName('Orchestrator'), 'Orchestrator (WALT)')
})

test('unknown dynamic specialists retain their backend name and role', () => {
  assert.deepEqual(agentPresentation('Custom Agent', 'Site specialist'), {
    name: 'Custom Agent',
    role: 'Site specialist',
  })
})

