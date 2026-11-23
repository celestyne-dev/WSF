import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cookieDomainsFor, createGa4, deleteGaCookies, gaCookieNames } from './ga4.js'

function fakeEnv(cookies = []) {
  const jar = new Map(cookies.map((c) => [c, '1']))
  const writes = []
  const appended = []
  const doc = {
    get cookie() {
      return [...jar.keys()].map((k) => `${k}=1`).join('; ')
    },
    set cookie(value) {
      writes.push(value)
      const name = value.split('=')[0]
      if (/expires=Thu, 01 Jan 1970/.test(value)) jar.delete(name)
      else jar.set(name, '1')
    },
    createElement: () => ({ dataset: {} }),
    head: { appendChild: (el) => appended.push(el) },
  }
  const win = { location: { hostname: 'www.womenshapingfutures.org', href: 'https://www.womenshapingfutures.org/x' } }
  return { win, doc, jar, writes, appended }
}

const commands = (win) => (win.dataLayer || []).map((args) => [...args])

test('no Measurement ID: nothing happens at all', () => {
  const env = fakeEnv()
  const ga = createGa4(env)
  ga.configure('')
  ga.applyConsent(true)
  ga.pageView('/x', 'X')
  assert.equal(env.win.dataLayer, undefined)
  assert.equal(env.appended.length, 0)
  ga.configure('not-an-id')
  ga.applyConsent(true)
  assert.equal(env.appended.length, 0)
})

test('ID without consent: Consent Mode v2 defaults all denied, no script', () => {
  const env = fakeEnv()
  const ga = createGa4(env)
  ga.configure('G-ABC123XYZ9')
  ga.applyConsent(false)
  assert.deepEqual(commands(env.win)[0], ['consent', 'default', {
    ad_storage: 'denied', analytics_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
  }])
  assert.equal(env.appended.length, 0)
  assert.equal(ga.active, false)
})

test('Analytics consent loads gtag.js once, grants analytics only, no Signals or ad features', () => {
  const env = fakeEnv()
  const ga = createGa4(env)
  ga.configure('G-ABC123XYZ9')
  ga.applyConsent(true)
  ga.applyConsent(true)
  assert.equal(env.appended.length, 1)
  assert.equal(env.appended[0].src, 'https://www.googletagmanager.com/gtag/js?id=G-ABC123XYZ9')
  const cmds = commands(env.win)
  assert.deepEqual(cmds.find((c) => c[0] === 'consent' && c[1] === 'update'), ['consent', 'update', { analytics_storage: 'granted' }])
  assert.ok(!cmds.some((c) => c[0] === 'consent' && c[1] === 'update' && Object.keys(c[2]).some((k) => k.startsWith('ad_'))))
  assert.deepEqual(cmds.find((c) => c[0] === 'config')[2], {
    send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false,
  })
  ga.pageView('/about', 'About')
  assert.deepEqual(commands(env.win).at(-1).slice(0, 2), ['event', 'page_view'])
})

test('withdrawal stops tracking and deletes only _ga / _ga_* cookies', () => {
  const env = fakeEnv(['_ga', '_ga_ABC123', '_gid_other', 'wsf_x', '_gat'])
  const ga = createGa4(env)
  ga.configure('G-ABC123XYZ9')
  ga.applyConsent(true)
  ga.applyConsent(false)
  assert.equal(env.win['ga-disable-G-ABC123XYZ9'], true)
  assert.deepEqual(commands(env.win).filter((c) => c[1] === 'update').at(-1), ['consent', 'update', { analytics_storage: 'denied' }])
  assert.deepEqual([...env.jar.keys()].sort(), ['_gat', '_gid_other', 'wsf_x'])
  const before = commands(env.win).length
  ga.pageView('/after', 'After')
  assert.equal(commands(env.win).length, before) // no events after withdrawal
  ga.applyConsent(true) // restored
  assert.equal(env.win['ga-disable-G-ABC123XYZ9'], false)
  assert.equal(env.appended.length, 1)
})

test('cookie helpers', () => {
  assert.deepEqual(cookieDomainsFor('www.womenshapingfutures.org'), [null, '.www.womenshapingfutures.org', '.womenshapingfutures.org'])
  assert.deepEqual(cookieDomainsFor('localhost'), [null])
  assert.deepEqual(cookieDomainsFor('127.0.0.1'), [null])
  assert.deepEqual(gaCookieNames('_ga=1; _ga_X=2; _gax=3; foo=4'), ['_ga', '_ga_X'])
  const env = fakeEnv(['_ga'])
  assert.deepEqual(deleteGaCookies(env.doc, 'localhost'), ['_ga'])
  assert.equal(env.writes[0], '_ga=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/')
})
