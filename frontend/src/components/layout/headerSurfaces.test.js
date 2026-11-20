import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// The header's floating panels obey Studio -> Settings -> Appearance
// (--wsf-radius-surface / -control); only intentionally circular controls
// keep rounded-full. Guards against a fixed radius creeping back in.
const read = (name) => readFileSync(new URL(`./${name}`, import.meta.url), 'utf8')
const FIXED_RADIUS = /\brounded(?:-(?:sm|md|lg|xl|2xl|3xl|\[[^\]]+\]))?(?=[\s"'`])/g

for (const file of ['MegaMenuPanel.jsx', 'AccountMenu.jsx']) {
  test(`${file}: panel uses rounded-surface, rows rounded-control, nothing fixed`, () => {
    const src = read(file)
    assert.match(src, /\brounded-surface\b/)
    assert.match(src, /\brounded-control\b/)
    assert.deepEqual(src.match(FIXED_RADIUS) || [], [])
  })
}
