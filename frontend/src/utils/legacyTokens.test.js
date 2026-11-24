import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { LEGACY_TOKEN_KEYS, purgeLegacyTokens } from './legacyTokens.js'

test('legacy localStorage tokens are removed and never kept', () => {
  const data = { wsf_access_token: 'old.jwt', wsf_refresh_token: 'old.refresh', wsf_cookie_consent: '{}' }
  const storage = { getItem: (k) => (k in data ? data[k] : null), removeItem: (k) => { delete data[k] } }
  assert.equal(purgeLegacyTokens(storage), 2)
  assert.deepEqual(Object.keys(data), ['wsf_cookie_consent'])
  assert.equal(purgeLegacyTokens(storage), 0)
  assert.doesNotThrow(() => purgeLegacyTokens(null))
})

function walk(dir, out = []) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, e.name)
    if (e.isDirectory()) walk(full, out)
    else if (/\.(jsx?)$/.test(e.name) && !e.name.includes('.test.')) out.push(full)
  }
  return out
}

test('no frontend code stores an auth token in browser storage', () => {
  const src = new URL('..', import.meta.url).pathname
  for (const file of walk(src)) {
    const text = readFileSync(file, 'utf8')
    for (const key of LEGACY_TOKEN_KEYS) {
      if (file.endsWith('legacyTokens.js')) continue
      assert.ok(!text.includes(key), `${file} still mentions ${key}`)
    }
    assert.ok(!/(localStorage|sessionStorage)\.setItem\([^)]*(token|Token)/.test(text), `${file} writes a token to storage`)
  }
})
