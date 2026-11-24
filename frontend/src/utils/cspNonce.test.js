import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readCspNonce } from './cspNonce.js'

const docWith = (value) => ({ querySelector: () => (value === null ? null : { getAttribute: () => value }) })

test('reads a well-formed nonce from the meta tag', () => {
  assert.equal(readCspNonce(docWith('AbC_def-1234567890xyz')), 'AbC_def-1234567890xyz')
})

test('missing or malformed nonce gives undefined', () => {
  assert.equal(readCspNonce(docWith(null)), undefined)
  assert.equal(readCspNonce(docWith('short')), undefined)
  assert.equal(readCspNonce(docWith('"><script>')), undefined)
  assert.equal(readCspNonce(null), undefined)
})
