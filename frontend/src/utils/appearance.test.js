import { test } from 'node:test'
import assert from 'node:assert/strict'
import { applyCornerStyle, CORNER_STYLES, resolveCornerStyle } from './appearance.js'

test('only the four presets are accepted; anything else falls back to square', () => {
  assert.deepEqual(CORNER_STYLES.map((c) => c.value), ['square', 'subtle', 'soft', 'rounded'])
  for (const v of ['square', 'subtle', 'soft', 'rounded']) assert.equal(resolveCornerStyle(v), v)
  for (const v of [undefined, null, '', '12px', 'border-radius:9px', 'ROUNDED']) assert.equal(resolveCornerStyle(v), 'square')
})

test('applyCornerStyle writes the data attribute and leaves an equal value untouched', () => {
  let writes = 0
  const dataset = {}
  const root = { dataset: new Proxy(dataset, { set(t, k, v) { writes += 1; t[k] = v; return true } }) }
  applyCornerStyle('soft', root)
  assert.equal(dataset.wsfCorners, 'soft')
  applyCornerStyle('soft', root)
  assert.equal(writes, 1)
  applyCornerStyle('<script>', root)
  assert.equal(dataset.wsfCorners, 'square')
})
