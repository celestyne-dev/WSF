// AI Search / GEO Phase 3A/4A — form helpers for Article/Person/Author
// sources (see components/cms/SourcesEditor.jsx). The backend's
// schemas/sources.py SourceSchema stays authoritative for validation.

export const MAX_SOURCES = 50

export function blankSource() {
  return { title: '', url: '', publisher: '', author: '', publishedDate: '', note: '' }
}

// Editable form value -> API payload: trimmed, empty optional fields dropped.
export function sourcesToPayload(sources) {
  return (sources || []).map((s) => {
    const out = { title: (s.title || '').trim(), url: (s.url || '').trim() }
    for (const key of ['publisher', 'author', 'publishedDate', 'note']) {
      const value = (s[key] || '').trim()
      if (value) out[key] = value
    }
    return out
  })
}

// Mirrors backend schemas/sources.py's validate_public_host() for the
// obvious cases: localhost, a single-label host ("intranet"), an IPv4/IPv6
// literal, or an all-digit top-level label. No DNS, no public-suffix list —
// the backend stays authoritative.
export function isPublicSourceHost(url) {
  let host
  try {
    host = new URL(url).hostname.toLowerCase().replace(/\.$/, '')
  } catch {
    return false
  }
  if (!host || host.startsWith('[') || host.includes(':')) return false
  if (host === 'localhost' || host.endsWith('.localhost')) return false
  const labels = host.split('.')
  if (labels.length < 2 || /^\d+$/.test(labels[labels.length - 1])) return false
  return true
}

// Quick client-side check so an editor sees the obvious problems before a
// round trip; returns a message or null. The backend re-validates.
export function validateSources(sources, noun = 'An article') {
  const seen = new Set()
  for (const [i, s] of sourcesToPayload(sources).entries()) {
    const label = `Source ${i + 1}`
    if (!s.title) return `${label} needs a title.`
    if (!/^https?:\/\/\S+$/i.test(s.url)) return `${label} needs a full http:// or https:// URL.`
    if (!isPublicSourceHost(s.url)) return `${label}: Source URL must use a public domain name.`
    if (seen.has(s.url)) return `${label} repeats a URL that's already listed.`
    seen.add(s.url)
  }
  if ((sources || []).length > MAX_SOURCES) return `${noun} can list at most ${MAX_SOURCES} sources.`
  return null
}

// The backend reports source problems either as a list-level message
// (duplicate URL / too many) or per item ({"1": {"url": ["Not a valid
// URL."]}}) — turned into one readable line for the toast.
export function describeSourceErrors(details) {
  if (!details) return null
  if (Array.isArray(details)) return details[0] || null
  const [index, fieldErrors] = Object.entries(details)[0] || []
  if (index === undefined) return null
  const [field, messages] = Object.entries(fieldErrors || {})[0] || []
  return `Source ${Number(index) + 1}${field ? ` (${field})` : ''}: ${Array.isArray(messages) ? messages[0] : 'invalid'}`
}
