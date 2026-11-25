import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')

test('email verification needs a button press (no auto-confirm on open)', () => {
  const src = read('./VerifyEmailPage.jsx')
  assert.doesNotMatch(src, /useEffect/)
  assert.match(src, /onClick=\{confirm\}/)
  assert.match(src, /Confirm my email address/)
})

test('unverified new accounts are routed to /verify-email from account and Studio', () => {
  for (const f of ['../layouts/AccountLayout.jsx', '../layouts/AdminLayout.jsx']) {
    assert.match(read(f), /emailVerificationPending\) return <Navigate to="\/verify-email"/)
  }
  assert.match(read('../api/auth.js'), /emailVerificationPending: !!u\.email_verification_pending/)
})
