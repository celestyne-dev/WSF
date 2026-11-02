// Plain-Node tests for the credential form helpers (backend
// schemas/credentials.py stays authoritative).
// Run with: node --test src/utils/credentials.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { credentialsToPayload, validateCredentials } from './credentials.js'

test('payload trims and drops empty optional fields', () => {
  assert.deepEqual(credentialsToPayload([{ name: '  MBA ', category: ' Degree ', issuer: '', url: '  ', note: '' }]), [{ name: 'MBA', category: 'Degree' }])
})

test('name required; links must be public http(s)', () => {
  assert.match(validateCredentials([{ name: '' }]), /needs a name/)
  for (const url of ['javascript:alert(1)', 'ftp://example.org/x', 'https://localhost/x', 'https://intranet/x', 'https://127.0.0.1/x', 'https://[::1]/x']) {
    assert.match(validateCredentials([{ name: 'X', url }]), /public domain name/, url)
  }
  assert.equal(validateCredentials([{ name: 'X', url: 'https://example.org/cred' }, { name: 'Y' }]), null)
})

test('duplicate name+issuer rejected; same name with another issuer allowed', () => {
  assert.match(validateCredentials([{ name: 'Certified X', issuer: 'Org A' }, { name: ' certified x ', issuer: 'ORG A' }]), /repeats a credential/)
  assert.equal(validateCredentials([{ name: 'Certified X', issuer: 'Org A' }, { name: 'Certified X', issuer: 'Org B' }]), null)
})

test('cap of 30', () => {
  const many = Array.from({ length: 31 }, (_, i) => ({ name: `C${i}` }))
  assert.match(validateCredentials(many), /at most 30 credentials/)
  assert.equal(validateCredentials(many.slice(0, 30)), null)
})
