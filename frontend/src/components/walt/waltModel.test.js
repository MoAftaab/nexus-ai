import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildWaltContextCards,
  CODEX_ATLAS_ROWS,
  getAtlasAnimation,
  isReviewContext,
  WALT_ANIMATION_STATES,
} from './waltModel.js'

test('every NexusAI WALT state resolves to a valid Codex atlas row', () => {
  assert.equal(WALT_ANIMATION_STATES.length, 16)
  for (const state of WALT_ANIMATION_STATES) {
    const animation = getAtlasAnimation(state)
    assert.ok(CODEX_ATLAS_ROWS[animation.id], `${state} must resolve to a supported atlas row`)
    assert.ok(animation.row >= 0 && animation.row <= 8)
    assert.ok(animation.frames >= 4 && animation.frames <= 8)
  }
})

test('WALT context cards derive values from live dashboard and anomaly records', () => {
  const cards = buildWaltContextCards(
    { metrics: [{ label: 'Exposure at risk', value: '€2.4M' }] },
    [
      { status: 'open', severity: 'critical', impact: 150000, system: 'WMS · ERP', evidence: [{}, {}] },
      { status: 'open', severity: 'medium', impact: 50000, systems: ['ERP'], evidence: [{}] },
      { status: 'resolved', severity: 'high', impact: 900000, systems: ['TMS'], evidence: [{}, {}] },
    ],
  )
  assert.deepEqual(cards.map(({ id, value }) => ({ id, value })), [
    { id: 'exposure', value: '€2.4M' },
    { id: 'priority', value: '1' },
    { id: 'evidence', value: '3' },
    { id: 'sources', value: '2' },
  ])
})

test('document and governed approval pages activate review mode', () => {
  assert.equal(isReviewContext('documents'), true)
  assert.equal(isReviewContext('changes'), true)
  assert.equal(isReviewContext('archive'), true)
  assert.equal(isReviewContext('command'), false)
})
