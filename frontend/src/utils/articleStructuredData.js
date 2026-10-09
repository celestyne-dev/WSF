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

  const { imageUrl, siteName, siteUrl, siteLogoUrl, authorBaseUrl } = options

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
  }
}
