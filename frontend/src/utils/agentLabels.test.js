import assert from 'node:assert/strict'
import test from 'node:test'
import { agentDisplayName, agentPresentation } from './agentLabels.js'

test('technical specialist names are presented in plain operational language', () => {
  assert.equal(agentDisplayName('Sentinel'), 'Issue Monitor')
  assert.equal(agentDisplayName('Correlator'), 'System Linker')
  assert.equal(agentDisplayName('Cascade'), 'Impact Tracer')
  assert.equal(agentDisplayName('Fix'), 'Action Planner')
})

test('unknown dynamic specialists retain their backend name and role', () => {
  assert.deepEqual(agentPresentation('Custom Agent', 'Site specialist'), {
    name: 'Custom Agent',
    role: 'Site specialist',
  })
})

