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
export function authorProfileModel(author, { articleCount = 0, page = 1 } = {}) {
  const firstName = authorFirstName(author?.name)
  const credentials = validCredentials(author)
  const programs = author?.authority?.learningPrograms || []
  const resources = author?.authority?.resources || []
  const about = hasBio(author)
  // Credentials sit beside About on wide screens; with no About they take
  // the main column instead, and with neither the profile band is skipped.
  const sidebar = about && credentials.length > 0
  const sections = []
  if (about || credentials.length) sections.push('profile')
  if (hasItems(programs)) sections.push('learning')
  if (hasItems(resources)) sections.push('resources')
  if (articleCount > 0 || page > 1) sections.push('articles')
  if (hasItems((author?.sources || []).filter((s) => s?.title))) sections.push('sources')
  return {
    firstName,
    headline: clean(author?.headline),
    roleLine: authorRoleLine(author),
    topics: (author?.topics || []).filter((t) => t?.slug && t?.name),
    stats: authorStatItems(author?.authority?.counts),
    links: authorExternalLinks(author),
    person: author?.person?.slug ? { slug: author.person.slug } : null,
    initials: authorInitials(author?.name),
    hasPortrait: Boolean(author?.photoMedia || author?.photo),
    about,
    credentials,
    sidebar,
    sections,
  }
}
