// AI Search / GEO Phase 4A/4B — pure, DOM-free builders for the schema.org
// JSON-LD on a Person profile (plain Person: an editorial subject, not
// necessarily affiliated with WSF) and an Author profile (a ProfilePage
// whose mainEntity is the Author's Person identity). Split out of
// the page hooks (which own only the <script> mechanics) so the data shape
// is exercised by plain `node --test` (profileStructuredData.test.js).
//
// Each mirrors backend/app/services/spa_shell.py key-for-key and in the
// same order (_build_person_json_ld / _build_author_json_ld), so React
// never swaps the server's JSON-LD for a different one after mount.
// Only stored, public facts: no inferred employer, award or credential;
// every optional key is conditionally spread in, never null or [].
// Editorial sources are `subjectOf` (works ABOUT the person) and never
// `sameAs` (identity URLs only).
import { sourceCreativeWorks } from './articleStructuredData.js'

const DEFAULT_SITE_URL = 'https://womenshapingfutures.org'

// Non-empty trimmed strings, case-insensitively deduplicated (first
// spelling kept) — spa_shell.py's _clean_strings().
export function cleanStrings(values) {
  const seen = new Set()
  const out = []
  for (const value of values || []) {
    if (typeof value !== 'string' || !value.trim()) continue
    const text = value.trim()
    if (seen.has(text.toLowerCase())) continue
    seen.add(text.toLowerCase())
    out.push(text)
  }
  return out
}

// Identity URLs only — spa_shell.py's _social_same_as().
export function profileSameAs(profile) {
  const social = profile?.social || {}
  const urls = [
    profile?.website,
    social.linkedin && `https://linkedin.com/in/${social.linkedin}`,
    social.twitter && `https://twitter.com/${social.twitter}`,
    social.instagram && `https://instagram.com/${social.instagram}`,
  ].filter(Boolean)
  return [...new Set(urls)]
}

// GEO Phase 4B — credentials as schema.org EducationalOccupationalCredential
// (`hasCredential`) — spa_shell.py's _profile_credentials(). `note` stays
// out; a credential URL is never identity (sameAs) or a work about the
// person (subjectOf).
export function profileCredentials(credentials) {
  return (credentials || [])
    .filter((c) => c?.name)
    .map((c) => ({
      '@type': 'EducationalOccupationalCredential',
      name: c.name,
      ...(c.category ? { credentialCategory: c.category } : {}),
      ...(c.issuer ? { recognizedBy: { '@type': 'Organization', name: c.issuer } } : {}),
      ...(c.url ? { url: c.url } : {}),
    }))
}

function base(siteUrl) {
  return (siteUrl || DEFAULT_SITE_URL).replace(/\/$/, '')
}

// `person` is the mapped public Person (api/people.js mapPerson): its
// `organization`/`organizationSlug` are only set when that Organization is
// published (PersonSchema.get_organization), so a draft one never reaches
// worksFor. `imageUrl` is passed in already resolved by the page.
export function buildPersonStructuredData(person, canonicalUrl, { imageUrl, siteUrl } = {}) {
  if (!person) return null
  const sameAs = profileSameAs(person)
  const knowsAbout = cleanStrings(person.expertise)
  const award = cleanStrings(person.awards)
  const hasCredential = profileCredentials(person.credentials)
  const subjectOf = sourceCreativeWorks(person.sources)
  return {
    '@context': 'https://schema.org',
    '@type': 'Person',
    name: person.name,
    url: canonicalUrl,
    ...(person.title ? { jobTitle: person.title } : {}),
    ...(person.organization && person.organizationSlug
      ? { worksFor: { '@type': 'Organization', name: person.organization, url: `${base(siteUrl)}/organizations/${person.organizationSlug}` } }
      : {}),
    ...(imageUrl ? { image: imageUrl } : {}),
    ...(sameAs.length ? { sameAs } : {}),
    ...(knowsAbout.length ? { knowsAbout } : {}),
    ...(award.length ? { award } : {}),
    ...(hasCredential.length ? { hasCredential } : {}),
    ...(subjectOf.length ? { subjectOf } : {}),
  }
}

// GEO Phase 4B — an Author page is a schema.org ProfilePage whose
// mainEntity is the Author's Person identity — spa_shell.py's
// _build_author_json_ld(). `author` is the mapped public Author
// (api/taxonomies.js mapAuthor): `topics` already published-only,
// createdAt/updatedAt the record's own timestamps passed through verbatim.
// No worksFor (a byline role is not employment), award, alumniOf or
// affiliation; never any account/user data.
export function buildAuthorProfilePageStructuredData(author, canonicalUrl, { imageUrl, siteUrl } = {}) {
  if (!author) return null
  const sameAs = profileSameAs(author)
  const seen = new Set()
  const knowsAbout = []
  const topics = (author.topics || []).filter((t) => t?.name && t?.slug && (!t.status || t.status === 'published'))
  for (const entry of [
    ...topics.map((t) => ({ '@type': 'Thing', name: t.name, url: `${base(siteUrl)}/topics/${t.slug}` })),
    ...cleanStrings(author.expertise),
  ]) {
    const key = (typeof entry === 'string' ? entry : entry.name).trim().toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    knowsAbout.push(entry)
  }
  const description = typeof author.shortBio === 'string' ? author.shortBio.trim() : ''
  const hasCredential = profileCredentials(author.credentials)
  const subjectOf = sourceCreativeWorks(author.sources)
  return {
    '@context': 'https://schema.org',
    '@type': 'ProfilePage',
    ...(author.createdAt ? { dateCreated: author.createdAt } : {}),
    ...(author.updatedAt ? { dateModified: author.updatedAt } : {}),
    mainEntity: {
      '@id': `${canonicalUrl}#author`,
      '@type': 'Person',
      name: author.name,
      url: canonicalUrl,
      ...(description ? { description } : {}),
      ...(author.role ? { jobTitle: author.role } : {}),
      ...(imageUrl ? { image: imageUrl } : {}),
      ...(sameAs.length ? { sameAs } : {}),
      ...(knowsAbout.length ? { knowsAbout } : {}),
      ...(hasCredential.length ? { hasCredential } : {}),
      ...(subjectOf.length ? { subjectOf } : {}),
    },
  }
}
