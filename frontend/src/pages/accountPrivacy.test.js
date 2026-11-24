import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// Step 16: what the member is told and asked before deletion, and how a
// scheduled account signs in (cancellation only).
const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')
const page = read('./AccountPrivacyPage.jsx')
const login = read('./LoginPage.jsx')

test('deletion page explains the 14-day grace period, comments, payments and asks for the password', () => {
  assert.match(page, /permanently deleted after 14 days/)
  assert.match(page, /“Former member”/)
  assert.match(page, /Also remove my comments/)
  assert.match(page, /Payment records are kept for 6 years/)
  assert.match(page, /type="password" required autoComplete="current-password"/)
  assert.match(page, /dispatch\(logout\(\)\)/)
})

test('export and privacy requests are offered', () => {
  assert.match(page, /Download my data/)
  assert.match(page, /We aim to reply within 30 days/)
})

test('a scheduled account is only offered cancellation at sign-in', () => {
  assert.match(login, /result\.payload\.deletionPending/)
  assert.match(login, /Cancel the deletion and sign in/)
  assert.match(login, /cancelDeletionWithLoginToken\(deletionStep\.cancelToken\)/)
})
