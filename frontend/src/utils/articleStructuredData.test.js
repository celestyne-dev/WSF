// Plain-Node tests for the pure Article JSON-LD builder — no test runner
// dependency needed (this repo currently has none; see Module 12A's
// report for why a DOM/React testing stack wasn't added just for this).
// Run with: node --test src/utils/articleStructuredData.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildArticleStructuredData } from './articleStructuredData.js'

const BASE_ARTICLE = {
  title: 'How Women Are Redefining Leadership',
  excerpt: 'A look at the shift.',
  publishDate: '2026-01-10T12:00:00Z',
  author: { slug: 'amara-otieno', name: 'Amara Otieno' },
}

test('returns null for no article', () => {
  assert.equal(buildArticleStructuredData(null, 'https://example.org/slug'), null)
})

test('builds the minimal real-data-only shape', () => {
  const data = buildArticleStructuredData(BASE_ARTICLE, 'https://example.org/slug')
  assert.equal(data['@context'], 'https://schema.org')
  assert.equal(data['@type'], 'Article')
  assert.equal(data.headline, BASE_ARTICLE.title)
  assert.equal(data.description, BASE_ARTICLE.excerpt)
  assert.equal(data.url, 'https://example.org/slug')
  assert.deepEqual(data.mainEntityOfPage, { '@type': 'WebPage', '@id': 'https://example.org/slug' })
  assert.equal(data.datePublished, new Date(BASE_ARTICLE.publishDate).toISOString())
  assert.deepEqual(data.author, { '@type': 'Person', name: 'Amara Otieno' })
  assert.equal(data.publisher.name, 'Women Shaping Futures')
})

test('never invents dateModified, image, or author url when not given', () => {
  const data = buildArticleStructuredData(BASE_ARTICLE, 'https://example.org/slug')
  assert.equal('dateModified' in data, false)
  assert.equal('image' in data, false)
  assert.equal('url' in data.author, false)
  assert.equal('url' in data.publisher, false)
  assert.equal('logo' in data.publisher, false)
})

test('uses the explicit SEO title/description over the fallback fields', () => {
  const article = { ...BASE_ARTICLE, seo: { title: 'SEO Title', description: 'SEO description' } }
  const data = buildArticleStructuredData(article, 'https://example.org/slug')
  assert.equal(data.headline, 'SEO Title')
  assert.equal(data.description, 'SEO description')
})

test('includes dateModified only when updatedDate is real', () => {
  const article = { ...BASE_ARTICLE, updatedDate: '2026-02-01T08:00:00Z' }
  const data = buildArticleStructuredData(article, 'https://example.org/slug')
  assert.equal(data.dateModified, new Date(article.updatedDate).toISOString())
})

test('includes image only when a resolved imageUrl is passed in', () => {
  const data = buildArticleStructuredData(BASE_ARTICLE, 'https://example.org/slug', {
    imageUrl: 'https://example.org/media/hero.webp',
  })
  assert.equal(data.image, 'https://example.org/media/hero.webp')
})

test('builds the author profile url only when a base url and slug are both real', () => {
  const withBase = buildArticleStructuredData(BASE_ARTICLE, 'https://example.org/slug', {
    authorBaseUrl: 'https://example.org/authors',
  })
  assert.equal(withBase.author.url, 'https://example.org/authors/amara-otieno')

  const withoutBase = buildArticleStructuredData(BASE_ARTICLE, 'https://example.org/slug')
  assert.equal('url' in withoutBase.author, false)
})

test('represents co-authors as an array, never dropping any of them', () => {
  const article = {
    ...BASE_ARTICLE,
    coAuthors: [
      { slug: 'binta-diallo', name: 'Binta Diallo' },
      { slug: 'lena-huang', name: 'Lena Huang' },
    ],
  }
  const data = buildArticleStructuredData(article, 'https://example.org/slug', {
    authorBaseUrl: 'https://example.org/authors',
  })
  assert.equal(Array.isArray(data.author), true)
  assert.equal(data.author.length, 3)
  assert.deepEqual(data.author.map((a) => a.name), ['Amara Otieno', 'Binta Diallo', 'Lena Huang'])
  assert.equal(data.author[1].url, 'https://example.org/authors/binta-diallo')
})

test('publisher reflects real configured site name/url/logo, nothing fabricated', () => {
  const data = buildArticleStructuredData(BASE_ARTICLE, 'https://example.org/slug', {
    siteName: 'Women Shaping Futures',
    siteUrl: 'https://womenshapingfutures.org',
    siteLogoUrl: 'https://womenshapingfutures.org/logo.webp',
  })
  assert.equal(data.publisher.name, 'Women Shaping Futures')
  assert.equal(data.publisher.url, 'https://womenshapingfutures.org')
  assert.deepEqual(data.publisher.logo, { '@type': 'ImageObject', url: 'https://womenshapingfutures.org/logo.webp' })
})

test('omits description entirely when neither seo.description nor excerpt exist', () => {
  const article = { title: 'No Excerpt', author: { slug: 'a', name: 'A' } }
  const data = buildArticleStructuredData(article, 'https://example.org/slug')
  assert.equal('description' in data, false)
})

test('has no author key at all when the article has no author', () => {
  const article = { title: 'No Author' }
  const data = buildArticleStructuredData(article, 'https://example.org/slug')
  assert.equal('author' in data, false)
})

// ArticlePage computes one effectiveCanonicalUrl (article.seo?.canonical ||
// the womenshapingfutures.org/{slug} fallback) and passes that SAME value
// to both useSeo's `canonical` (-> <link rel="canonical"> and og:url) and
// this builder's `canonicalUrl` param — these two tests exercise both
// branches of that selection the way ArticlePage actually computes it, to
// guard against url/mainEntityOfPage.@id ever drifting from the canonical
// link/og:url that useSeo renders.
test('url and mainEntityOfPage.@id use the normal WSF fallback canonical when no CMS override is set', () => {
  const article = { ...BASE_ARTICLE, seo: {} }
  const fallbackUrl = 'https://womenshapingfutures.org/how-women-are-redefining-leadership'
  const effectiveCanonicalUrl = article.seo?.canonical || fallbackUrl
  const data = buildArticleStructuredData(article, effectiveCanonicalUrl)
  assert.equal(effectiveCanonicalUrl, fallbackUrl)
  assert.equal(data.url, fallbackUrl)
  assert.deepEqual(data.mainEntityOfPage, { '@type': 'WebPage', '@id': fallbackUrl })
})

test('url and mainEntityOfPage.@id use the editor-supplied CMS canonical override, not the WSF fallback', () => {
  const overrideUrl = 'https://partner-site.example.com/syndicated/how-women-are-redefining-leadership'
  const article = { ...BASE_ARTICLE, seo: { canonical: overrideUrl } }
  const fallbackUrl = 'https://womenshapingfutures.org/how-women-are-redefining-leadership'
  const effectiveCanonicalUrl = article.seo?.canonical || fallbackUrl
  const data = buildArticleStructuredData(article, effectiveCanonicalUrl)
  assert.equal(effectiveCanonicalUrl, overrideUrl)
  assert.equal(data.url, overrideUrl)
  assert.deepEqual(data.mainEntityOfPage, { '@type': 'WebPage', '@id': overrideUrl })
  assert.notEqual(data.url, fallbackUrl)
})
