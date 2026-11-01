// Plain-Node tests for the pure Person/Author JSON-LD builders (GEO Phase
// 4A). Expected objects match backend tests/test_profile_evidence_geo_
// phase4a.py's server JSON-LD assertions for the same inputs, so server/
// client parity is explicit.
// Run with: node --test src/utils/profileStructuredData.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildAuthorStructuredData, buildPersonStructuredData, cleanStrings, profileSameAs } from './profileStructuredData.js'

const SITE = 'https://womenshapingfutures.org'
const SOURCE_A = {
  title: 'Appointed CEO of Example Bank',
  url: 'https://news.example.org/ceo-appointment',
  publisher: 'Example News',
  author: 'Business Desk',
  publishedDate: '2025-06-30',
  note: 'Confirms appointment as CEO.',
}
const SOURCE_B = { title: 'Institutional biography', url: 'https://bank.example.com/about/leadership' }

test('returns null without a profile', () => {
  assert.equal(buildPersonStructuredData(null, `${SITE}/people/x`), null)
  assert.equal(buildAuthorStructuredData(undefined, `${SITE}/authors/x`), null)
})

test('minimal Person has no empty or null fields', () => {
  const data = buildPersonStructuredData({ name: 'Jane', expertise: [], awards: [], sources: [], social: {} }, `${SITE}/people/jane`)
  assert.deepEqual(data, { '@context': 'https://schema.org', '@type': 'Person', name: 'Jane', url: `${SITE}/people/jane` })
})

test('full Person: identity sameAs, knowsAbout, award, worksFor and subjectOf', () => {
  const person = {
    name: 'Jane',
    title: 'Chief Executive',
    organization: 'Example Bank',
    organizationSlug: 'example-bank',
    website: 'https://jane.example.com',
    social: { linkedin: 'jane', twitter: 'jane_x', instagram: 'jane_ig' },
    expertise: ['Finance', ' finance ', '', 'Leadership'],
    awards: ['Banker of the Year 2024', '  '],
    sources: [SOURCE_A, SOURCE_B],
  }
  const data = buildPersonStructuredData(person, `${SITE}/people/jane`, { imageUrl: `${SITE}/media/jane.jpg` })
  assert.deepEqual(Object.keys(data), ['@context', '@type', 'name', 'url', 'jobTitle', 'worksFor', 'image', 'sameAs', 'knowsAbout', 'award', 'subjectOf'])
  assert.deepEqual(data.worksFor, { '@type': 'Organization', name: 'Example Bank', url: `${SITE}/organizations/example-bank` })
  assert.deepEqual(data.sameAs, ['https://jane.example.com', 'https://linkedin.com/in/jane', 'https://twitter.com/jane_x', 'https://instagram.com/jane_ig'])
  assert.deepEqual(data.knowsAbout, ['Finance', 'Leadership'])
  assert.deepEqual(data.award, ['Banker of the Year 2024'])
  assert.deepEqual(data.subjectOf, [
    {
      '@type': 'CreativeWork',
      name: SOURCE_A.title,
      url: SOURCE_A.url,
      author: { '@type': 'Thing', name: 'Business Desk' },
      publisher: { '@type': 'Organization', name: 'Example News' },
      datePublished: '2025-06-30',
    },
    { '@type': 'CreativeWork', name: SOURCE_B.title, url: SOURCE_B.url },
  ])
  // Evidence URLs never become identity; notes never reach JSON-LD.
  assert.ok(!data.sameAs.includes(SOURCE_A.url) && !data.sameAs.includes(SOURCE_B.url))
  assert.ok(!JSON.stringify(data).includes('Confirms appointment'))
})

test('Person without a published Organization (no slug) gets no worksFor', () => {
  const data = buildPersonStructuredData({ name: 'Jane', organization: null, organizationSlug: null }, `${SITE}/people/jane`)
  assert.equal(data.worksFor, undefined)
})

test('Author: Instagram in sameAs, published Topics + expertise in knowsAbout, no invented employer/award', () => {
  const author = {
    name: 'Writer',
    role: 'Contributor',
    website: 'https://writer.example.com',
    social: { linkedin: 'writer', instagram: 'writer_ig' },
    topics: [
      { slug: 'leadership', name: 'Leadership', status: 'published' },
      { slug: 'secret-topic', name: 'Secret Draft Topic', status: 'draft' },
    ],
    expertise: ['leadership', 'Climate finance'],
    sources: [SOURCE_A],
  }
  const data = buildAuthorStructuredData(author, `${SITE}/authors/writer`)
  assert.deepEqual(Object.keys(data), ['@context', '@type', 'name', 'url', 'jobTitle', 'sameAs', 'knowsAbout', 'subjectOf'])
  assert.deepEqual(data.sameAs, ['https://writer.example.com', 'https://linkedin.com/in/writer', 'https://instagram.com/writer_ig'])
  assert.deepEqual(data.knowsAbout, [{ '@type': 'Thing', name: 'Leadership', url: `${SITE}/topics/leadership` }, 'Climate finance'])
  assert.equal(data.subjectOf[0].url, SOURCE_A.url)
  assert.ok(!data.sameAs.includes(SOURCE_A.url))
  assert.equal(data.worksFor, undefined)
  assert.equal(data.award, undefined)
})

test('minimal Author has no empty or null fields', () => {
  const data = buildAuthorStructuredData({ name: 'W', topics: [], expertise: [], sources: [], social: {} }, `${SITE}/authors/w`)
  assert.deepEqual(data, { '@context': 'https://schema.org', '@type': 'Person', name: 'W', url: `${SITE}/authors/w` })
})

test('helpers dedupe conservatively', () => {
  assert.deepEqual(cleanStrings(['A', 'a', ' A ', 'B', null, 3]), ['A', 'B'])
  assert.deepEqual(profileSameAs({ website: 'https://x.org', social: {} }), ['https://x.org'])
})
