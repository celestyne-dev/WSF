import test from 'node:test'
import assert from 'node:assert/strict'
import { isPopupExcludedPath, isPopupSuppressed, popupTriggerReached, readPopupState, writePopupState, POPUP_STORAGE_KEY } from './newsletterPopup.js'

const settings = { delaySeconds: 15, scrollPercent: 45, dismissDays: 14, successDays: 365 }
const DAY = 86400000

test('excluded routes', () => {
  for (const p of ['/admin', '/admin/jobs', '/login', '/register', '/reset-password', '/forgot-password', '/newsletter', '/newsletter/unsubscribe/abc',
    '/privacy', '/terms', '/cookies', '/resources/checkout/callback', '/circle/checkout/callback', '/certificates/verify/X1', '/account/profile',
    '/learning/course/lessons/4', '/submit', '/lifetime']) {
    assert.equal(isPopupExcludedPath(p), true, p)
  }
  for (const p of ['/', '/jobs', '/opportunities/grant', '/learning', '/learning/course', '/some-article', '/newsletters-and-more']) {
    assert.equal(isPopupExcludedPath(p), false, p)
  }
})

test('delayed trigger, scroll trigger, whichever first', () => {
  assert.equal(popupTriggerReached({ elapsedMs: 14999, scrollPercent: 10 }, settings), false)
  assert.equal(popupTriggerReached({ elapsedMs: 15000, scrollPercent: 0 }, settings), true)
  assert.equal(popupTriggerReached({ elapsedMs: 1000, scrollPercent: 45 }, settings), true)
  assert.equal(popupTriggerReached({ elapsedMs: 0, scrollPercent: 0 }, { ...settings, delaySeconds: 0 }), false)
  assert.equal(popupTriggerReached({ elapsedMs: 99999, scrollPercent: 99 }, { ...settings, delaySeconds: 0, scrollPercent: 0 }), false)
})

test('dismissal and success suppression windows', () => {
  const now = Date.parse('2026-11-21T12:00:00Z')
  assert.equal(isPopupSuppressed({}, settings, now), false)
  assert.equal(isPopupSuppressed({ dismissedAt: new Date(now - 13 * DAY).toISOString() }, settings, now), true)
  assert.equal(isPopupSuppressed({ dismissedAt: new Date(now - 15 * DAY).toISOString() }, settings, now), false)
  assert.equal(isPopupSuppressed({ subscribedAt: new Date(now - 300 * DAY).toISOString() }, settings, now), true)
  assert.equal(isPopupSuppressed({ dismissedAt: 'garbage' }, settings, now), false)
})

test('state storage is tolerant', () => {
  const data = {}
  const store = { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v } }
  writePopupState(store, { dismissedAt: '2026-11-21T00:00:00Z' })
  assert.ok(data[POPUP_STORAGE_KEY])
  assert.deepEqual(readPopupState(store), { dismissedAt: '2026-11-21T00:00:00Z' })
  assert.deepEqual(readPopupState({ getItem: () => '{bad' }), {})
  assert.deepEqual(readPopupState({ getItem: () => { throw new Error('x') } }), {})
})

// --- storage depends on Preferences consent ---------------------------------------------
import { POPUP_STORAGE_KEY as KEY, popupStorageFor, syncPopupStorage } from './newsletterPopup.js'

function memStore(initial = {}) {
  const data = { ...initial }
  return { data, getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v) }, removeItem: (k) => { delete data[k] } }
}

test('popup state uses localStorage only with Preferences consent', () => {
  const local = memStore(), session = memStore()
  assert.equal(popupStorageFor(true, { local, session }), local)
  assert.equal(popupStorageFor(false, { local, session }), session)
})

test('withdrawing Preferences removes the persistent copy and keeps a session one', () => {
  const state = JSON.stringify({ dismissedAt: '2026-11-20T10:00:00.000Z' })
  const local = memStore({ [KEY]: state }), session = memStore()
  syncPopupStorage(false, { local, session })
  assert.equal(local.data[KEY], undefined)
  assert.equal(session.data[KEY], state)
})

test('granting Preferences carries the session state into localStorage', () => {
  const state = JSON.stringify({ subscribedAt: '2026-11-20T10:00:00.000Z' })
  const local = memStore(), session = memStore({ [KEY]: state })
  syncPopupStorage(true, { local, session })
  assert.equal(local.data[KEY], state)
  assert.equal(session.data[KEY], undefined)
})

test('an existing destination value is kept, and missing storage is harmless', () => {
  const local = memStore({ [KEY]: '{"dismissedAt":"old"}' }), session = memStore({ [KEY]: '{"dismissedAt":"new"}' })
  syncPopupStorage(false, { local, session })
  assert.equal(session.data[KEY], '{"dismissedAt":"new"}')
  assert.equal(local.data[KEY], undefined)
  assert.doesNotThrow(() => syncPopupStorage(true, {}))
})
