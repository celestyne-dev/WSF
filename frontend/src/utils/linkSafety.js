// Client mirror of backend content_blocks.safe_link_url(): the CTA and
// Simple CTA blocks may only link to an internal WSF path or an http(s)
// URL. The server already sanitizes on save; this guards the editor
// preview and any unsaved/legacy data. Never javascript:, data:, "//".
const INTERNAL_RE = /^\/(?!\/)[^\s\\<>"']*$/
const EXTERNAL_RE = /^https?:\/\/[^\s<>"']+$/i
const MAILTO_RE = /^mailto:[^\s<>"']+@[^\s<>"']+$/i
const RESERVED = ['/admin', '/api']

// eslint-disable-next-line no-control-regex
const CONTROL_RE = /[\u0000-\u001f\u007f]/

export function safeLinkUrl(value, { allowMailto = false } = {}) {
  if (typeof value !== 'string') return ''
  const url = value.trim()
  if (!url || CONTROL_RE.test(url)) return ''
  if (allowMailto && MAILTO_RE.test(url)) return url
  if (INTERNAL_RE.test(url)) {
    const path = url.split('#')[0].split('?')[0].toLowerCase().replace(/\/+$/, '')
    if (RESERVED.some((p) => path === p || path.startsWith(`${p}/`))) return ''
    return url
  }
  if (EXTERNAL_RE.test(url)) return url
  return ''
}

export function isInternalPath(url) {
  return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//')
}

// Turns what an editor types into the link prompt into a safe href, or an
// explanation of why it can't be used (never a silently dropped link).
const EMAIL_RE = /^[^\s@<>"']+@[^\s@<>"']+\.[^\s@<>"']+$/
const BARE_DOMAIN_RE = /^[a-z0-9-]+(\.[a-z0-9-]+)+(\/[^\s]*)?$/i

export function normalizeEditorLink(raw) {
  let url = typeof raw === 'string' ? raw.trim() : ''
  if (!url) return { error: 'Enter a link address.' }
  if (EMAIL_RE.test(url)) url = `mailto:${url}`
  else if (/^www\./i.test(url) || BARE_DOMAIN_RE.test(url)) url = `https://${url}`
  const safe = safeLinkUrl(url, { allowMailto: true })
  if (!safe) {
    return { error: 'That link can’t be used. Use a site path like /resources/salary-guide, a full https:// address, or an email address.' }
  }
  return { url: safe }
}
