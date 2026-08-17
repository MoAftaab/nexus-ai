import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTheme, normalizeTheme } from './theme.js'

test('legacy and invalid themes normalize to the requested light/dark system', () => {
  assert.equal(normalizeTheme('vw', false), 'dark')
  assert.equal(normalizeTheme('default', false), 'light')
  assert.equal(normalizeTheme('unknown', true), 'dark')
})

test('theme toggle alternates between white and dark modes', () => {
  assert.equal(nextTheme('light'), 'dark')
  assert.equal(nextTheme('dark'), 'light')
})
