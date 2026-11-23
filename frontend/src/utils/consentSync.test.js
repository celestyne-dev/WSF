import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createConsentSync } from './consentSync.js'

const choice = { version: '1', timestamp: '2026-11-23T10:00:00.000Z', preferences: false, analytics: true, marketing: false }

test('anonymous visitors and undecided states are never sent', () => {
  const sent = []
  const sync = createConsentSync((c) => sent.push(c))
  assert.equal(sync({ userId: null, choice }), false)
  assert.equal(sync({ userId: 7, choice: null }), false)
  assert.equal(sent.length, 0)
})

test('one decision is sent once per member, a new decision is sent again', async () => {
  const sent = []
  const sync = createConsentSync((c) => sent.push(c))
  assert.equal(sync({ userId: 7, choice }), true)
  assert.equal(sync({ userId: 7, choice }), false)
  assert.equal(sync({ userId: 7, choice: { ...choice, timestamp: '2026-11-23T11:00:00.000Z' } }), true)
  assert.equal(sync({ userId: 8, choice }), true) // another member signs in on this device
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(sent.length, 3)
})

test('a failed send is retried on the next call', async () => {
  let fail = true
  const sync = createConsentSync(() => (fail ? Promise.reject(new Error('offline')) : Promise.resolve()))
  sync({ userId: 7, choice })
  await new Promise((r) => setTimeout(r, 0))
  fail = false
  assert.equal(sync({ userId: 7, choice }), true)
})
