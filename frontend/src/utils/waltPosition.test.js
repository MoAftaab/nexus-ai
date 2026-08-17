import test from 'node:test'
import assert from 'node:assert/strict'
import {
  calculateWaltPopupPosition,
  clampWaltPosition,
  findWaltRoamPosition,
  isDragGesture,
  isWaltPositionClear,
  parseStoredWaltPosition,
} from './waltPosition.js'

test('WALT stays at the exact valid release point instead of snapping', () => {
  assert.deepEqual(
    clampWaltPosition({ x: 427, y: 263 }, { width: 1200, height: 800 }, { width: 168, height: 152 }),
    { x: 427, y: 263 },
  )
})

test('the popup opens left of WALT near the right edge and stays in the viewport', () => {
  const placement = calculateWaltPopupPosition(
    { x: 1018, y: 320, width: 168, height: 152 },
    { width: 1200, height: 800 },
    { width: 580, height: 680 },
  )
  assert.equal(placement.direction, 'left')
  assert.ok(placement.x + placement.width < 1018)
  assert.ok(placement.x >= 12 && placement.y >= 12)
  assert.ok(placement.x + placement.width <= 1188)
  assert.ok(placement.y + placement.height <= 788)
})

test('the popup opens right of WALT near the left edge', () => {
  const placement = calculateWaltPopupPosition(
    { x: 12, y: 300, width: 168, height: 152 },
    { width: 1200, height: 800 },
    { width: 580, height: 680 },
  )
  assert.equal(placement.direction, 'right')
  assert.ok(placement.x > 180)
})

test('the popup uses vertical space on a narrow mobile viewport without covering WALT', () => {
  const placement = calculateWaltPopupPosition(
    { x: 130, y: 700, width: 126, height: 116 },
    { width: 390, height: 844 },
    { width: 580, height: 680 },
  )
  assert.equal(placement.direction, 'above')
  assert.ok(placement.y + placement.height < 700)
  assert.ok(placement.width <= 366)
})

test('the popup opens downward when mobile WALT is near the top', () => {
  const placement = calculateWaltPopupPosition(
    { x: 130, y: 12, width: 126, height: 116 },
    { width: 390, height: 844 },
    { width: 580, height: 680 },
  )
  assert.equal(placement.direction, 'below')
  assert.ok(placement.y > 128)
})

test('the popup remains visible when the mobile keyboard leaves a very short viewport', () => {
  const viewport = { width: 390, height: 220 }
  const popup = calculateWaltPopupPosition({ x: 246, y: 92, width: 126, height: 116 }, viewport, { width: 580, height: 680 })
  assert.ok(popup.x >= 12 && popup.y >= 12)
  assert.ok(popup.x + popup.width <= viewport.width - 12)
  assert.ok(popup.y + popup.height <= viewport.height - 12)
})

test('autonomous roaming remains local and rejects occupied candidates', () => {
  const target = findWaltRoamPosition(
    { x: 700, y: 500 },
    { width: 1200, height: 800 },
    { width: 168, height: 152 },
    [{ left: 820, right: 950, top: 430, bottom: 720 }],
  )
  assert.ok(Math.hypot(target.x - 700, target.y - 500) <= 90)
  assert.ok(target.x + 168 <= 820 || target.x >= 950 || target.y + 152 <= 430 || target.y >= 720)
})

test('WALT detects when its position would cover an important control', () => {
  const size = { width: 168, height: 152 }
  const controls = [{ left: 900, right: 1040, top: 100, bottom: 145 }]
  assert.equal(isWaltPositionClear({ x: 880, y: 80 }, size, controls), false)
  assert.equal(isWaltPositionClear({ x: 620, y: 300 }, size, controls), true)
})

test('WALT finds a viewport-wide fallback when all local safety nudges are occupied', () => {
  const size = { width: 168, height: 152 }
  const occupied = [{ left: 380, right: 980, top: 180, bottom: 700 }]
  const target = findWaltRoamPosition(
    { x: 700, y: 420 },
    { width: 1200, height: 800 },
    size,
    occupied,
    220,
  )
  assert.notDeepEqual(target, { x: 700, y: 420 })
  assert.equal(isWaltPositionClear(target, size, occupied), true)
})

const pet = { width: 116, height: 92 }

test('WALT distinguishes a click from an intentional drag', () => {
  assert.equal(isDragGesture({ x: 100, y: 100 }, { x: 104, y: 103 }), false)
  assert.equal(isDragGesture({ x: 100, y: 100 }, { x: 108, y: 100 }), true)
})

test('WALT remains fully visible after a resize', () => {
  assert.deepEqual(
    clampWaltPosition({ x: 1100, y: 760 }, { width: 500, height: 420 }, pet),
    { x: 372, y: 316 },
  )
})

test('WALT safely ignores corrupt stored coordinates', () => {
  assert.deepEqual(parseStoredWaltPosition('{"x":42,"y":80}'), { x: 42, y: 80 })
  assert.equal(parseStoredWaltPosition('{"x":"outside"}'), null)
  assert.equal(parseStoredWaltPosition('not-json'), null)
})
