// Pure helpers for the public Author authority profile (Node-testable).
// Counts are derived server-side (app/services/author_authority.py) —
// never stored — and only non-zero ones are shown. Everything here reads
// the existing Author payload; nothing is invented or hardcoded.

export function authorStatItems(counts) {
  const items = [
    [counts?.articles, 'Article', 'Articles'],
    [counts?.resources, 'Career Tool', 'Career Tools'],
    [counts?.courses, 'Course', 'Courses'],
  ]
  return items
    .filter(([n]) => Number.isInteger(n) && n > 0)
    .map(([n, one, many]) => ({ value: n, label: n === 1 ? one : many }))
}

// "Learn with Celestine" — the first word of the display name.
export function authorFirstName(name) {
  return (name || '').trim().split(/\s+/)[0] || ''
}

// Whether a bounded section should render at all (never an empty shell).
export function hasItems(list) {
  return Array.isArray(list) && list.length > 0
}

const clean = (value) => (typeof value === 'string' ? value.trim() : '')

// "Nairobi, Kenya" from location + country without repeating the country
// when the editor already typed it into the location.
export function authorPlace(author) {
  const location = clean(author?.location)
  const country = clean(author?.country?.name)
  if (location && country && !location.toLowerCase().includes(country.toLowerCase())) return `${location}, ${country}`
  return location || country
}

// "Founder & Editor · Nairobi, Kenya" — the role exactly as entered.
export function authorRoleLine(author) {
  return [clean(author?.role), authorPlace(author)].filter(Boolean).join(' · ')
}

const SOCIAL = [
  ['linkedin', 'LinkedIn', (v) => `https://www.linkedin.com/in/${v}`],
  ['twitter', 'X (Twitter)', (v) => `https://x.com/${v}`],
  ['instagram', 'Instagram', (v) => `https://www.instagram.com/${v}`],
]

const isHttpUrl = (value) => /^https?:\/\/[^\s]+$/i.test(value)

// External links shown with visible text. A social handle may be a bare
// username (the Studio convention) or a full URL; anything else is dropped.
export function authorExternalLinks(author) {
  const links = []
  const website = clean(author?.website)
  if (isHttpUrl(website)) links.push({ kind: 'website', label: 'Website', href: website })
  for (const [key, label, build] of SOCIAL) {
    const raw = clean(author?.social?.[key]).replace(/^@/, '')
    if (!raw) continue
    if (isHttpUrl(raw)) links.push({ kind: key, label, href: raw })
    else if (/^[A-Za-z0-9._-]+$/.test(raw)) links.push({ kind: key, label, href: build(raw) })
  }
  return links
}

// Up to two letters for the portrait fallback ("Celestine Nyamoita" -> "CN").
export function authorInitials(name) {
  const parts = clean(name).split(/\s+/).filter(Boolean)
  if (!parts.length) return ''
  const first = parts[0][0] || ''
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ''
  return `${first}${last}`.toUpperCase()
}

const validCredentials = (author) => (author?.credentials || []).filter((c) => c?.name)
const hasBio = (author) => Array.isArray(author?.bio) && author.bio.length > 0

// The whole page composition, in document order. Each section appears only
// when it has real content, so no empty heading can ever render.
// Education for the profile facts, derived from credentials an editor
// already entered (no separate field): degree-type categories or degree
// names. At most two, "Name, Issuer". Mirrors backend prerender
// author_education(); both are tested against tests/fixtures/
// author_education_cases.json.
const EDUCATION_CATEGORY = /\b(degree|education|academic|diploma)\b/i
const EDUCATION_NAME = /^(b\.?a\b|b\.?sc|ba\b|bsc|ma\b|msc|mba|phd|ph\.d|llb|llm|bachelor|master|doctor|doctorate)/i

export function authorEducation(credentials) {
  return (Array.isArray(credentials) ? credentials : [])
    .filter((c) => c && clean(c.name) && (EDUCATION_CATEGORY.test(c.category || '') || EDUCATION_NAME.test(clean(c.name))))
    .slice(0, 2)
    .map((c) => [clean(c.name), clean(c.issuer)].filter(Boolean).join(', '))
}

export function authorProfileModel(author, { articleCount = 0, page = 1 } = {}) {
  const firstName = authorFirstName(author?.name)
  const credentials = validCredentials(author)
  const programs = author?.authority?.learningPrograms || []
  const resources = author?.authority?.resources || []
  const about = hasBio(author)
  // Profile order (Author redesign): About, then Credentials as their own
  // section, Learn with, Career tools, the article archive, Sources.
  const sections = []
  if (about) sections.push('about')
  if (credentials.length) sections.push('credentials')
  if (hasItems(programs)) sections.push('learning')
  if (hasItems(resources)) sections.push('resources')
  if (articleCount > 0 || page > 1) sections.push('articles')
  if (hasItems((author?.sources || []).filter((s) => s?.title))) sections.push('sources')
  const headline = clean(author?.headline)
  const role = clean(author?.role)
  const topics = (author?.topics || []).filter((t) => t?.slug && t?.name)
  const education = authorEducation(credentials)
  // Hero facts: only labels with a value. Role is a fact only when the
  // headline already took the line under the name (otherwise the role is
  // that line, and repeating it would duplicate it).
  const facts = []
  const place = authorPlace(author)
  if (place) facts.push({ key: 'location', label: 'Location', values: [place] })
  if (headline && role) facts.push({ key: 'role', label: 'Role', values: [role] })
  if (education.length) facts.push({ key: 'education', label: 'Education', values: education })
  if (topics.length) facts.push({ key: 'topics', label: 'Areas of expertise', topics })
  return {
    firstName,
    headline,
    // The line under the name: the headline, else the role.
    subtitle: headline || role,
    roleLine: authorRoleLine(author),
    role,
    place,
    intro: clean(author?.shortBio),
    education,
    topics,
    facts,
    links: authorExternalLinks(author),
    person: author?.person?.slug ? { slug: author.person.slug } : null,
    initials: authorInitials(author?.name),
    hasPortrait: Boolean(author?.photoMedia || author?.photo),
    about,
    credentials,
    sections,
  }
}

// Maps the server's one-shot Author bootstrap ({key, data: {author,
// authority, articles, meta}}, see backend spa_shell._safe_public_author_payload)
// into exactly the state AuthorProfilePage builds from its API calls:
// `author` = fetchAuthorBySlug()'s shape, `articles`/`pagination` =
// fetchArticles({author, page: 1})'s shape. The mappers are injected so this
// stays Node-testable. Returns null when there is nothing usable (the caller
// then fetches normally). Slug matching is readBootstrap's job.
export function authorBootstrapState(payload, { mapAuthor, mapArticle }) {
  const data = payload?.data
  if (!data || typeof data !== 'object' || !data.author || typeof data.author !== 'object') return null
  const meta = data.meta
  return {
    author: { ...mapAuthor(data.author), authority: data.authority || null },
    articles: Array.isArray(data.articles) ? data.articles.map(mapArticle) : [],
    pagination: meta
      ? { page: meta.page, pageSize: meta.per_page, totalItems: meta.total, totalPages: meta.total_pages }
      : null,
  }
}
