// AI Search / GEO Phase 4B — form helpers for Person/Author credentials &
// qualifications (components/cms/CredentialsEditor.jsx). The backend's
// schemas/credentials.py CredentialSchema stays authoritative.
import { isPublicSourceHost } from './sources.js'

export const MAX_CREDENTIALS = 30

export function blankCredential() {
  return { name: '', category: '', issuer: '', url: '', note: '' }
}

// Editable form value -> API payload: trimmed, empty optional fields dropped.
export function credentialsToPayload(credentials) {
  return (credentials || []).map((c) => {
    const out = { name: (c.name || '').trim() }
    for (const key of ['category', 'issuer', 'url', 'note']) {
      const value = (c[key] || '').trim()
      if (value) out[key] = value
    }
    return out
  })
}

// Quick client-side check; returns a message or null. Duplicate identity is
// name + issuer (case/space-insensitive), the same key the backend uses.
export function validateCredentials(credentials, noun = 'A profile') {
  const seen = new Set()
  for (const [i, c] of credentialsToPayload(credentials).entries()) {
    const label = `Credential ${i + 1}`
    if (!c.name) return `${label} needs a name.`
    if (c.url && (!/^https?:\/\/\S+$/i.test(c.url) || !isPublicSourceHost(c.url))) {
      return `${label}: the link must be a full http(s) URL on a public domain name.`
    }
    const key = `${c.name.toLowerCase()}\u0000${(c.issuer || '').toLowerCase()}`
    if (seen.has(key)) return `${label} repeats a credential (same name and issuer) that's already listed.`
    seen.add(key)
  }
  if ((credentials || []).length > MAX_CREDENTIALS) return `${noun} can list at most ${MAX_CREDENTIALS} credentials.`
  return null
}

// The API's `credentials` field error -> one readable line for the toast.
export function describeCredentialErrors(details) {
  if (!details) return null
  if (Array.isArray(details)) return details[0] || null
  const [index, fieldErrors] = Object.entries(details)[0] || []
  if (index === undefined) return null
  const [field, messages] = Object.entries(fieldErrors || {})[0] || []
  return `Credential ${Number(index) + 1}${field ? ` (${field})` : ''}: ${Array.isArray(messages) ? messages[0] : 'invalid'}`
}
