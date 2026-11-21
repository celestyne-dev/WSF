import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CONSENT_STORAGE_KEY, _setStorageForTests, acceptAllConsent, configureConsentVersion, getConsent, hasConsent,
  needsConsentDecision, onConsentChange, onOpenConsentManager, openConsentManager, rejectOptionalConsent, saveConsent,
} from './consent.js'

function fakeStorage(initial = {}) {
  const data = { ...initial }
  return { data, getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v) }, removeItem: (k) => { delete data[k] } }
}

test('no stored preference: decision needed, nothing optional allowed, essential always', () => {
  _setStorageForTests(fakeStorage())
  assert.equal(hasConsent('analytics'), false) // version not known yet
  configureConsentVersion('1')
  assert.equal(needsConsentDecision(), true)
  for (const c of ['preferences', 'analytics', 'marketing']) assert.equal(hasConsent(c), false)
  assert.equal(hasConsent('essential'), true)
})

test('accept all, reject optional, granular choice', () => {
  const store = fakeStorage()
  _setStorageForTests(store)
  configureConsentVersion('1')
  acceptAllConsent(new Date('2026-11-21T10:00:00Z'))
  assert.deepEqual(JSON.parse(store.data[CONSENT_STORAGE_KEY]), { version: '1', timestamp: '2026-11-21T10:00:00.000Z', preferences: true, analytics: true, marketing: true })
  assert.equal(hasConsent('marketing'), true)
  rejectOptionalConsent()
  assert.equal(hasConsent('analytics'), false)
  assert.equal(needsConsentDecision(), false) // a rejection is a decision
  saveConsent({ analytics: true })
  assert.equal(hasConsent('analytics'), true)
  assert.equal(hasConsent('marketing'), false)
  assert.equal(hasConsent('preferences'), false)
})

test('a new consent version asks again', () => {
  _setStorageForTests(fakeStorage())
  configureConsentVersion('1')
  acceptAllConsent()
  configureConsentVersion('2')
  assert.equal(getConsent(), null)
  assert.equal(needsConsentDecision(), true)
  assert.equal(hasConsent('analytics'), false)
})

test('deleted, malformed or partial storage never means yes', () => {
  for (const raw of [undefined, 'not json', '{"version":"1"}', '{"version":"1","timestamp":"x","preferences":"yes","analytics":true,"marketing":true}']) {
    _setStorageForTests(fakeStorage(raw === undefined ? {} : { [CONSENT_STORAGE_KEY]: raw }))
    configureConsentVersion('1')
    assert.equal(hasConsent('analytics'), false, raw)
    assert.equal(needsConsentDecision(), true, raw)
  }
})

test('withdrawal notifies listeners immediately; reopen events', () => {
  _setStorageForTests(fakeStorage())
  configureConsentVersion('1')
  const seen = []
  const off = onConsentChange((s) => seen.push(s.analytics))
  acceptAllConsent()
  rejectOptionalConsent()
  off()
  acceptAllConsent()
  assert.deepEqual(seen, [true, false])
  let opened = 0
  onOpenConsentManager(() => { opened += 1 })
  openConsentManager()
  assert.equal(opened, 1)
})

test('storage that throws keeps the choice in memory for the page', () => {
  _setStorageForTests({ getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') }, removeItem() {} })
  configureConsentVersion('1')
  assert.equal(hasConsent('analytics'), false)
  saveConsent({ analytics: true })
  assert.equal(hasConsent('analytics'), true)
})
