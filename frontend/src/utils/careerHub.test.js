// Plain-Node tests for the WSF Career Hub URL state and card display rules.
// Run with: node --test src/utils/careerHub.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_SORT,
  buildHubSearch,
  cardAccessLine,
  cardCircleLine,
  cardEyebrow,
  cardMetaLine,
  cardPriceLine,
  describeResults,
  hubRequestParams,
  isFiltering,
  parseHubParams,
  resetHubState,
  updateHubState,
} from './careerHub.js'

const META = {
  goals: [{ slug: 'get-promoted', label: 'Get promoted' }, { slug: 'earn-more', label: 'Earn more' }],
  formats: [{ slug: 'workbook', label: 'Workbook' }, { slug: 'course', label: 'Course' }, { slug: 'learning-series', label: 'Learning series' }],
  access: [{ slug: 'free', label: 'Free' }, { slug: 'circle', label: 'WSF Circle' }, { slug: 'premium', label: 'Premium' }],
  sorts: [{ slug: 'newest' }, { slug: 'featured' }, { slug: 'recently-added' }],
}

const params = (text) => new URLSearchParams(text)

test('a direct filtered URL reproduces the same state', () => {
  const state = parseHubParams(params('goal=leadership&format=course&access=circle&sort=featured&page=3&q=negotiate'), META)
  assert.deepEqual(state, { q: 'negotiate', goal: 'leadership', format: 'course', access: 'circle', sort: 'featured', page: 3 })
  assert.equal(buildHubSearch(state), '?q=negotiate&goal=leadership&format=course&access=circle&sort=featured&page=3')
})

test('unknown or malformed values are dropped, never passed on', () => {
  const state = parseHubParams(params('format=video&access=everything&sort=most-read&page=-2&goal=<script>'), META)
  assert.deepEqual(state, { q: '', goal: '', format: '', access: '', sort: DEFAULT_SORT, page: 1 })
})

test('goal accepts canonical goals and topic-slug aliases', () => {
  assert.equal(parseHubParams(params('goal=get-promoted'), META).goal, 'get-promoted')
  assert.equal(parseHubParams(params('goal=salary-negotiation'), META).goal, 'salary-negotiation')
})

test('before meta loads, values are kept so the first request matches the URL', () => {
  assert.equal(parseHubParams(params('format=workbook&access=premium'), null).format, 'workbook')
})

test('canonical query string omits defaults and keeps a stable order', () => {
  assert.equal(buildHubSearch(resetHubState()), '')
  assert.equal(buildHubSearch({ ...resetHubState(), access: 'free', goal: 'earn-more' }), '?goal=earn-more&access=free')
  assert.equal(buildHubSearch({ ...resetHubState(), q: '  ' }), '')
})

test('changing any filter resets to page 1; changing page keeps filters', () => {
  const onPage3 = { ...resetHubState(), goal: 'earn-more', page: 3 }
  assert.equal(updateHubState(onPage3, { format: 'workbook' }).page, 1)
  const paged = updateHubState(onPage3, { page: 4 })
  assert.equal(paged.page, 4)
  assert.equal(paged.goal, 'earn-more')
})

test('filtering detection, reset and request params', () => {
  assert.equal(isFiltering(resetHubState()), false)
  assert.equal(isFiltering({ ...resetHubState(), access: 'free' }), true)
  assert.deepEqual(hubRequestParams({ ...resetHubState(), goal: 'earn-more', page: 2 }), { page: 2, pageSize: 12, sort: 'newest', goal: 'earn-more' })
})

const premiumCard = {
  category: { name: 'Salary & Negotiation' },
  goal: { label: 'Earn more' },
  format: { label: 'Playbook' },
  estimatedTime: { label: '45–60 min' },
  access: { level: 'premium', label: 'Premium' },
  circle: { included: true, scope: 'all', label: 'Included with WSF Circle' },
  pricing: {
    oneTime: true,
    defaultCurrency: 'KES',
    prices: [
      { currency: 'USD', formatted: 'US$19.00', checkoutAvailable: true },
      { currency: 'KES', formatted: 'KES 1,500', checkoutAvailable: true },
    ],
  },
}

test('card shows format, time, one-time price and Circle inclusion together', () => {
  assert.equal(cardEyebrow(premiumCard), 'Salary & Negotiation')
  assert.equal(cardMetaLine(premiumCard), 'Playbook · 45–60 min')
  assert.equal(cardPriceLine(premiumCard), 'KES 1,500 one-time')
  assert.equal(cardCircleLine(premiumCard), 'Included with WSF Circle')
  assert.equal(cardAccessLine(premiumCard), null)
})

test('yearly-level and non-included items are worded accurately', () => {
  const yearly = { access: { level: 'circle', label: 'WSF Circle Yearly & Lifetime' }, circle: { included: true, label: 'Included with Yearly & Lifetime WSF Circle' } }
  assert.equal(cardCircleLine(yearly), 'Included with Yearly & Lifetime WSF Circle')
  const product = { access: { level: 'premium', label: 'Premium' }, circle: { included: false, label: null }, pricing: { defaultCurrency: 'USD', prices: [{ currency: 'USD', formatted: 'US$45.00' }] } }
  assert.equal(cardCircleLine(product), null)
  assert.equal(cardPriceLine(product), 'US$45.00 one-time')
  const free = { access: { level: 'free', label: 'Free' }, circle: { included: false } }
  assert.equal(cardAccessLine(free), 'Free')
  assert.equal(cardMetaLine({ format: { label: 'Guide' } }), 'Guide')
  assert.equal(cardEyebrow({ goal: { label: 'Earn more' } }), 'Earn more')
})

test('results announcement names the active filters', () => {
  assert.equal(describeResults(1, resetHubState(), META), '1 tool')
  assert.equal(describeResults(4, { ...resetHubState(), goal: 'get-promoted', format: 'workbook' }, META), '4 tools for Get promoted, Workbook')
})
