// Plain-Node tests for the pure Person/Author JSON-LD builders (GEO Phase
// 4A). Expected objects match backend tests/test_profile_evidence_geo_
// phase4a.py's server JSON-LD assertions for the same inputs, so server/
// client parity is explicit.
// Run with: node --test src/utils/profileStructuredData.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildAuthorProfilePageStructuredData, buildPersonStructuredData, cleanStrings, profileSameAs } from './profileStructuredData.js'

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
  assert.equal(buildAuthorProfilePageStructuredData(undefined, `${SITE}/authors/x`), null)
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

const CREDENTIAL = {
  name: 'Certified Digital Marketing Professional',
  category: 'Professional certification',
  issuer: 'Digital Marketing Institute',
  url: 'https://example.org/dmi',
  note: 'Completed professional certification.',
}
const CREDENTIAL_LD = {
  '@type': 'EducationalOccupationalCredential',
  name: 'Certified Digital Marketing Professional',
  credentialCategory: 'Professional certification',
  recognizedBy: { '@type': 'Organization', name: 'Digital Marketing Institute' },
  url: 'https://example.org/dmi',
}

test('Person stays a plain Person and gains hasCredential (no note)', () => {
  const data = buildPersonStructuredData(
    { name: 'Jane', expertise: ['Finance'], awards: ['Award'], sources: [SOURCE_B], credentials: [CREDENTIAL, { name: 'MBA' }], social: { linkedin: 'jane' } },
    `${SITE}/people/jane`,
  )
  assert.equal(data['@type'], 'Person')
  assert.deepEqual(Object.keys(data), ['@context', '@type', 'name', 'url', 'sameAs', 'knowsAbout', 'award', 'hasCredential', 'subjectOf'])
  assert.deepEqual(data.hasCredential, [CREDENTIAL_LD, { '@type': 'EducationalOccupationalCredential', name: 'MBA' }])
  assert.ok(!JSON.stringify(data).includes('Completed professional certification'))
})

// Same fixture as backend test_profile_credentials_geo_phase4b.py's
// test_author_profile_page_json_ld, so server/client parity is explicit.
const AUTHOR = {
  name: 'Writer',
  role: 'Contributor',
  shortBio: '  Writes about work and money.  ',
  website: 'https://writer.example.com',
  social: { linkedin: 'writer', instagram: 'writer_ig' },
  topics: [
    { slug: 'leadership', name: 'Leadership', status: 'published' },
    { slug: 'secret-topic', name: 'Secret Draft Topic', status: 'draft' },
  ],
  expertise: ['leadership', 'Climate finance'],
  sources: [SOURCE_A],
  credentials: [CREDENTIAL],
  createdAt: '2026-01-02T03:04:05.123456+00:00',
  updatedAt: '2026-02-03T04:05:06.654321+00:00',
}

test('Author page is a ProfilePage whose mainEntity is the Person identity', () => {
  const canonical = `${SITE}/authors/writer`
  const data = buildAuthorProfilePageStructuredData(AUTHOR, canonical)
  assert.deepEqual(data, {
    '@context': 'https://schema.org',
    '@type': 'ProfilePage',
    dateCreated: '2026-01-02T03:04:05.123456+00:00',
    dateModified: '2026-02-03T04:05:06.654321+00:00',
    mainEntity: {
      '@id': `${canonical}#author`,
      '@type': 'Person',
      name: 'Writer',
      url: canonical,
      description: 'Writes about work and money.',
      jobTitle: 'Contributor',
      sameAs: ['https://writer.example.com', 'https://linkedin.com/in/writer', 'https://instagram.com/writer_ig'],
      knowsAbout: [{ '@type': 'Thing', name: 'Leadership', url: `${SITE}/topics/leadership` }, 'Climate finance'],
      hasCredential: [CREDENTIAL_LD],
      subjectOf: [
        {
          '@type': 'CreativeWork',
          name: SOURCE_A.title,
          url: SOURCE_A.url,
          author: { '@type': 'Thing', name: 'Business Desk' },
          publisher: { '@type': 'Organization', name: 'Example News' },
          datePublished: '2025-06-30',
        },
      ],
    },
  })
})

test('credential URL is in hasCredential only — never sameAs or subjectOf', () => {
  const entity = buildAuthorProfilePageStructuredData(AUTHOR, `${SITE}/authors/writer`).mainEntity
  assert.equal(entity.hasCredential[0].url, CREDENTIAL.url)
  assert.ok(!entity.sameAs.includes(CREDENTIAL.url))
  assert.ok(!entity.subjectOf.some((w) => w.url === CREDENTIAL.url))
  for (const invented of ['worksFor', 'award', 'alumniOf', 'affiliation', 'memberOf', 'email', 'identifier']) {
    assert.equal(entity[invented], undefined, invented)
  }
})

test('minimal Author ProfilePage has no empty fields or invented dates', () => {
  const data = buildAuthorProfilePageStructuredData({ name: 'W', shortBio: '  ', topics: [], expertise: [], sources: [], credentials: [], social: {} }, `${SITE}/authors/w`)
  assert.deepEqual(data, {
    '@context': 'https://schema.org',
    '@type': 'ProfilePage',
    mainEntity: { '@id': `${SITE}/authors/w#author`, '@type': 'Person', name: 'W', url: `${SITE}/authors/w` },
  })
})

test('helpers dedupe conservatively', () => {
  assert.deepEqual(cleanStrings(['A', 'a', ' A ', 'B', null, 3]), ['A', 'B'])
  assert.deepEqual(profileSameAs({ website: 'https://x.org', social: {} }), ['https://x.org'])
})
