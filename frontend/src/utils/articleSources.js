// AI Search / GEO Phase 3A — form helpers for Article.sources (see
// components/cms/ArticleSourcesEditor.jsx). The backend's
// ArticleSourceSchema stays authoritative for validation.

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

// Quick client-side check so an editor sees the obvious problems before a
// round trip; returns a message or null. The backend re-validates.
export function validateSources(sources) {
  const seen = new Set()
  for (const [i, s] of sourcesToPayload(sources).entries()) {
    const label = `Source ${i + 1}`
    if (!s.title) return `${label} needs a title.`
    if (!/^https?:\/\/\S+$/i.test(s.url)) return `${label} needs a full http:// or https:// URL.`
    if (seen.has(s.url)) return `${label} repeats a URL that's already listed.`
    seen.add(s.url)
  }
  if ((sources || []).length > MAX_SOURCES) return `An article can list at most ${MAX_SOURCES} sources.`
  return null
}
