// Pure, DOM-free builder for an Article's schema.org JSON-LD object.
// Deliberately split out of the useArticleStructuredData effect hook in
// ArticlePage.jsx (which owns the <script> create/update/cleanup
// mechanics, mirroring useEventStructuredData/useResourceStructuredData/
// useJobStructuredData) so this part — the actual data shape — can be
// exercised by a plain `node --test` run with zero DOM/React/env
// dependency (see articleStructuredData.test.js).
//
// Every optional key is conditionally spread in, never set to null/"" —
// same discipline as the other per-page structured-data builders: nothing
// here is fabricated to "complete" the schema.
//
// `imageUrl` and `imageAlt` are passed in already-resolved (same values
// ArticlePage gives useSeo for og:image/og:image:alt) rather than
// re-derived here, so there is exactly one place that decides the social
// image priority (explicit SEO image -> hero image -> absent).
export function buildArticleStructuredData(article, canonicalUrl, options = {}) {
  if (!article) return null

  const { imageUrl, siteName, siteUrl, siteLogoUrl, authorBaseUrl, entityBaseUrl } = options

  const headline = article.seo?.title || article.title
  const description = article.seo?.description || article.excerpt

  const authorList = [article.author, ...(article.coAuthors || [])].filter(Boolean)
  const authors = authorList.map((person) => ({
    '@type': 'Person',
    name: person.name,
    ...(person.slug && authorBaseUrl ? { url: `${authorBaseUrl}/${person.slug}` } : {}),
  }))

  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline,
    ...(description ? { description } : {}),
    mainEntityOfPage: { '@type': 'WebPage', '@id': canonicalUrl },
    url: canonicalUrl,
    ...(imageUrl ? { image: imageUrl } : {}),
    ...(article.publishDate ? { datePublished: new Date(article.publishDate).toISOString() } : {}),
    ...(article.updatedDate ? { dateModified: new Date(article.updatedDate).toISOString() } : {}),
    ...(authors.length === 1 ? { author: authors[0] } : authors.length > 1 ? { author: authors } : {}),
    publisher: {
      '@type': 'Organization',
      name: siteName || 'Women Shaping Futures',
      ...(siteUrl ? { url: siteUrl } : {}),
      ...(siteLogoUrl ? { logo: { '@type': 'ImageObject', url: siteLogoUrl } } : {}),
    },
    ...articleEntityFields(article, entityBaseUrl),
  }
}

const isPublished = (item) => item?.status === 'published'

// AI Search / GEO Phase 3A — articleSection/keywords/about/mentions/
// citation, from the article's own editorial relationships and editor-
// entered sources only (never inferred from its text). Only PUBLISHED
// taxonomy terms / People / Organizations count. Mirrors
// backend/app/services/spa_shell.py's _article_entity_fields() key-for-
// key and in the same order, so React never swaps the server's JSON-LD
// for a reduced version after mount. `entityBaseUrl` is the site origin
// (ArticlePage passes the same one it uses for author URLs).
export function articleEntityFields(article, entityBaseUrl) {
  const base = (entityBaseUrl || '').replace(/\/$/, '')
  const withUrl = (path) => (base ? { url: `${base}${path}` } : {})
  const category = isPublished(article.category) ? article.category : null
  const topics = (article.topics || []).filter(isPublished)
  const tags = (article.tags || []).filter(isPublished)
  const fields = {}

  const section = category ? category.name : topics[0]?.name
  if (section) fields.articleSection = section

  const seen = new Set()
  const keywords = []
  for (const name of [...topics.map((t) => t.name), ...tags.map((t) => t.name)]) {
    if (name && !seen.has(name.toLowerCase())) {
      seen.add(name.toLowerCase())
      keywords.push(name)
    }
  }
  if (keywords.length) fields.keywords = keywords.join(', ')

  const about = topics.map((t) => ({ '@type': 'Thing', name: t.name, ...withUrl(`/topics/${t.slug}`) }))
  if (category && !topics.some((t) => t.name.toLowerCase() === category.name.toLowerCase())) {
    about.push({ '@type': 'Thing', name: category.name })
  }
  if (about.length) fields.about = about

  const mentions = [
    ...(article.relatedPeople || []).filter(isPublished).map((p) => ({ '@type': 'Person', name: p.name, ...withUrl(`/people/${p.slug}`) })),
    ...(article.relatedOrganizations || [])
      .filter(isPublished)
      .map((o) => ({ '@type': 'Organization', name: o.name, ...withUrl(`/organizations/${o.slug}`) })),
  ]
  if (mentions.length) fields.mentions = mentions

  const citation = (article.sources || [])
    .filter((s) => s?.title && s?.url)
    .map((s) => ({
      '@type': 'CreativeWork',
      name: s.title,
      url: s.url,
      ...(s.author ? { author: { '@type': 'Thing', name: s.author } } : {}),
      ...(s.publisher ? { publisher: { '@type': 'Organization', name: s.publisher } } : {}),
      ...(s.publishedDate ? { datePublished: s.publishedDate } : {}),
    }))
  if (citation.length) fields.citation = citation

  return fields
}
