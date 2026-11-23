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

test('the placeholder names the provider from the player host itself', async () => {
  const { embedProviderLabel } = await import('./videoEmbed.js')
  assert.equal(embedProviderLabel('https://www.youtube-nocookie.com/embed/abc'), 'YouTube')
  assert.equal(embedProviderLabel('https://player.vimeo.com/video/1'), 'Vimeo')
  assert.equal(embedProviderLabel('https://fast.wistia.net/embed/iframe/x'), 'Wistia')
  assert.equal(embedProviderLabel('https://www.loom.com/embed/x'), 'Loom')
  assert.equal(embedProviderLabel('https://evil.example/embed/x'), null)
})

test('"Always allow videos" grants Preferences only and keeps the other choices', async () => {
  const { grantConsentCategory, getConsent } = await import('./consent.js')
  _setStorageForTests(store())
  configureConsentVersion('1')
  saveConsent({ analytics: true, marketing: false })
  grantConsentCategory('preferences')
  const c = getConsent()
  assert.deepEqual([c.preferences, c.analytics, c.marketing], [true, true, false])
  assert.equal(show(YT), true)

  _setStorageForTests(store()) // undecided visitor: the grant is their decision, nothing else turned on
  configureConsentVersion('1')
  grantConsentCategory('preferences')
  const d = getConsent()
  assert.deepEqual([d.preferences, d.analytics, d.marketing], [true, false, false])
  assert.equal(grantConsentCategory('essential'), null)
})

test('"Play video" loads only the requested video and changes no consent', () => {
  _setStorageForTests(store())
  configureConsentVersion('1')
  assert.equal(show(YT, { playRequested: true }), true)
  assert.equal(hasConsent('preferences'), false)
  assert.equal(show('https://player.vimeo.com/video/2'), false) // another video stays a placeholder
})
