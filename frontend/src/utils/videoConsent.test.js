import test from 'node:test'
import assert from 'node:assert/strict'
import { _setStorageForTests, configureConsentVersion, hasConsent, rejectOptionalConsent, saveConsent } from './consent.js'
import { shouldShowPlayer } from './videoEmbed.js'

const YT = 'https://www.youtube-nocookie.com/embed/abc123'
const store = () => {
  const d = {}
  return { getItem: (k) => d[k] ?? null, setItem: (k, v) => { d[k] = v }, removeItem: (k) => { delete d[k] } }
}
const show = (url, extra = {}) => shouldShowPlayer(url, { preferencesConsent: hasConsent('preferences'), ...extra })

test('no consent: no iframe; Play loads that video', () => {
  _setStorageForTests(store())
  configureConsentVersion('1')
  assert.equal(show(YT), false)
  assert.equal(show(YT, { playRequested: true }), true)
})

test('Preferences consent allows players; Marketing-only does not', () => {
  _setStorageForTests(store())
  configureConsentVersion('1')
  saveConsent({ preferences: true })
  assert.equal(show(YT), true)
  saveConsent({ marketing: true })
  assert.equal(show(YT), false)
})

test('withdrawing Preferences unloads a consent-loaded player', () => {
  _setStorageForTests(store())
  configureConsentVersion('1')
  saveConsent({ preferences: true })
  assert.equal(show(YT), true)
  rejectOptionalConsent()
  assert.equal(show(YT), false)
})

test('unsafe or non-allowlisted URLs never become an iframe', () => {
  for (const url of ['https://evil.example/embed/x', 'javascript:alert(1)', 'http://www.youtube-nocookie.com/embed/x', '', null]) {
    assert.equal(shouldShowPlayer(url, { preferencesConsent: true, playRequested: true }), false, String(url))
  }
})
