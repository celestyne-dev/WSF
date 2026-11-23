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

test('a choice expires 12 calendar months after it was made and is removed', async () => {
  const { _setClockForTests, consentExpiresAt } = await import('./consent.js')
  const store = fakeStorage()
  _setStorageForTests(store)
  configureConsentVersion('1')
  _setClockForTests(() => new Date('2025-11-23T09:00:00Z'))
  acceptAllConsent()
  assert.equal(consentExpiresAt('2025-11-23T09:00:00Z').toISOString(), '2026-11-23T09:00:00.000Z')

  _setClockForTests(() => new Date('2026-11-23T08:59:59Z')) // one second before expiry
  assert.equal(hasConsent('analytics'), true)
  assert.equal(needsConsentDecision(), false)

  _setClockForTests(() => new Date('2026-11-23T09:00:00Z')) // expired
  assert.equal(hasConsent('analytics'), false)
  assert.equal(needsConsentDecision(), true)
  assert.equal(store.data[CONSENT_STORAGE_KEY], undefined) // removed, not just ignored
})

test('a version change re-asks before 12 months; unreadable timestamps never count', async () => {
  const { _setClockForTests } = await import('./consent.js')
  const store = fakeStorage()
  _setStorageForTests(store)
  _setClockForTests(() => new Date('2026-02-01T00:00:00Z'))
  configureConsentVersion('1')
  acceptAllConsent(new Date('2026-01-01T00:00:00Z'))
  assert.equal(hasConsent('analytics'), true)
  configureConsentVersion('2')
  assert.equal(needsConsentDecision(), true)

  store.data[CONSENT_STORAGE_KEY] = JSON.stringify({ version: '2', timestamp: 'garbage', preferences: true, analytics: true, marketing: true })
  assert.equal(hasConsent('analytics'), false)
  assert.equal(store.data[CONSENT_STORAGE_KEY], undefined)
})

test('Global Privacy Control: Marketing is rejected and cannot be enabled; other categories unaffected', async () => {
  const { _setGpcForTests, consentSnapshot } = await import('./consent.js')
  const store = fakeStorage()
  _setStorageForTests(store)
  configureConsentVersion('1')
  _setGpcForTests(true)
  acceptAllConsent()
  assert.equal(JSON.parse(store.data[CONSENT_STORAGE_KEY]).marketing, false) // recorded as rejected
  assert.equal(hasConsent('marketing'), false)
  assert.equal(hasConsent('analytics'), true)
  assert.equal(hasConsent('preferences'), true)
  saveConsent({ marketing: true })
  assert.equal(hasConsent('marketing'), false)
  assert.equal(consentSnapshot().gpc, true)
  assert.equal(consentSnapshot().marketing, false)

  // A choice stored before GPC was switched on still can't grant Marketing.
  _setGpcForTests(false)
  acceptAllConsent()
  assert.equal(hasConsent('marketing'), true)
  _setGpcForTests(true)
  assert.equal(hasConsent('marketing'), false)
})

// --- Batch 1 review: GPC is reflected in what is stored and synced ------------------------
test('GPC review: stored Marketing=true is effective only while GPC is off', async () => {
  const { _setGpcForTests, _setClockForTests } = await import('./consent.js')
  const store = fakeStorage()
  _setStorageForTests(store)
  _setClockForTests(() => new Date('2026-11-22T10:00:00Z'))
  configureConsentVersion('1')
  acceptAllConsent()
  _setGpcForTests(false)
  assert.equal(hasConsent('marketing'), true) // GPC off: effective true
  assert.equal(getConsent().marketing, true)

  _setClockForTests(() => new Date('2026-11-23T09:00:00Z'))
  _setGpcForTests(true)
  assert.equal(hasConsent('marketing'), false) // GPC on: effective false
  const normalized = getConsent()
  assert.deepEqual(
    { v: normalized.version, p: normalized.preferences, a: normalized.analytics, m: normalized.marketing },
    { v: '1', p: true, a: true, m: false },
  )
  // A new decision: new timestamp, original decision kept as the expiry basis.
  assert.equal(normalized.timestamp, '2026-11-23T09:00:00.000Z')
  assert.equal(normalized.expiresFrom, '2026-11-22T10:00:00.000Z')
  assert.equal(JSON.parse(store.data[CONSENT_STORAGE_KEY]).marketing, false) // stored choice no longer claims true
  // Normalizing twice is a no-op (no second new decision).
  assert.equal(getConsent().timestamp, '2026-11-23T09:00:00.000Z')
})

test('GPC review: normalization never extends the 12 months from the original decision', async () => {
  const { _setGpcForTests, _setClockForTests } = await import('./consent.js')
  _setStorageForTests(fakeStorage())
  _setClockForTests(() => new Date('2025-12-01T00:00:00Z'))
  configureConsentVersion('1')
  acceptAllConsent()
  _setGpcForTests(true)
  _setClockForTests(() => new Date('2026-11-01T00:00:00Z'))
  getConsent() // normalized on 2026-11-01
  _setClockForTests(() => new Date('2026-12-01T00:00:01Z')) // 12 months after the ORIGINAL decision
  assert.equal(getConsent(), null)
})

test('GPC review: Accept all with GPC stores Marketing=false; Preferences/Analytics exactly as chosen', async () => {
  const { _setGpcForTests } = await import('./consent.js')
  const store = fakeStorage()
  _setStorageForTests(store)
  configureConsentVersion('1')
  _setGpcForTests(true)
  acceptAllConsent()
  assert.deepEqual(JSON.parse(store.data[CONSENT_STORAGE_KEY]).marketing, false)
  saveConsent({ preferences: false, analytics: true, marketing: true })
  const c = getConsent()
  assert.deepEqual([c.preferences, c.analytics, c.marketing], [false, true, false])
})

test('GPC review: switching GPC off later does not resurrect Marketing', async () => {
  const { _setGpcForTests } = await import('./consent.js')
  _setStorageForTests(fakeStorage())
  configureConsentVersion('1')
  _setGpcForTests(false)
  acceptAllConsent()
  _setGpcForTests(true)
  assert.equal(hasConsent('marketing'), false) // normalized here
  _setGpcForTests(false)
  assert.equal(hasConsent('marketing'), false) // still rejected: must be granted again
  saveConsent({ preferences: true, analytics: true, marketing: true }) // explicit new grant
  assert.equal(hasConsent('marketing'), true)
})
