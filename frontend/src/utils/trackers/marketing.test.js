import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createLinkedInInsight, createMetaPixel, deleteMetaCookies, needsReload } from './marketing.js'

function env(cookies = []) {
  const jar = new Set(cookies)
  const appended = []
  const doc = {
    get cookie() {
      return [...jar].map((k) => `${k}=1`).join('; ')
    },
    set cookie(v) {
      const name = v.split('=')[0]
      if (/1970/.test(v)) jar.delete(name)
      else jar.add(name)
    },
    createElement: () => ({ dataset: {} }),
    head: { appendChild: (el) => appended.push(el) },
  }
  return { win: { location: { hostname: 'womenshapingfutures.org' } }, doc, jar, appended }
}

test('LinkedIn: inactive without an ID or without Marketing consent', () => {
  const e = env()
  const li = createLinkedInInsight(e)
  li.applyConsent(true) // no ID
  li.configure('abc') // invalid ID
  li.applyConsent(true)
  li.configure('1234567')
  li.applyConsent(false)
  assert.equal(e.appended.length, 0)
  assert.equal(e.win._linkedin_partner_id, undefined)
  li.applyConsent(true)
  li.applyConsent(true)
  assert.equal(e.appended.length, 1)
  assert.equal(e.appended[0].src, 'https://snap.licdn.com/li.lms-analytics/insight.min.js')
  assert.deepEqual(e.win._linkedin_data_partner_ids, ['1234567'])
})

test('Meta: inactive without ID/consent; grant, no autoConfig, PageView, revoke and cookie removal', () => {
  const e = env(['_fbp', '_fbc', 'wsf_x'])
  const px = createMetaPixel(e)
  px.configure('123456789012345')
  px.applyConsent(false)
  assert.equal(e.win.fbq, undefined)
  assert.equal(e.appended.length, 0)
  px.applyConsent(true)
  assert.equal(e.appended[0].src, 'https://connect.facebook.net/en_US/fbevents.js')
  const q = () => e.win.fbq.queue.map((args) => args.slice(0, 3))
  assert.deepEqual(q().slice(0, 3), [['consent', 'grant'], ['set', 'autoConfig', false], ['init', '123456789012345']])
  px.pageView()
  assert.deepEqual(q().at(-1), ['track', 'PageView'])
  px.applyConsent(false)
  assert.deepEqual(q().at(-1), ['consent', 'revoke'])
  assert.deepEqual([...e.jar], ['wsf_x'])
  const n = q().length
  px.pageView()
  assert.equal(q().length, n) // nothing after withdrawal
})

test('withdrawal needs a reload only when a marketing script ran on this page', () => {
  assert.equal(needsReload({ linkedin: { loaded: false }, meta: { loaded: false } }, false), false)
  assert.equal(needsReload({ linkedin: { loaded: true }, meta: { loaded: false } }, false), true)
  assert.equal(needsReload({ linkedin: { loaded: true }, meta: { loaded: true } }, true), false)
  assert.deepEqual(deleteMetaCookies(env(['_fbp']).doc, 'localhost'), ['_fbp'])
})
