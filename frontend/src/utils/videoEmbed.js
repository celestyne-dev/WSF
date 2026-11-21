// Defence in depth for video embeds. The backend derives embed URLs for
// YouTube, Vimeo, Wistia and Loom only (app/services/video_embed.py); the
// browser still refuses to iframe anything that is not https on one of
// those players' own hosts. Everything else is a plain outbound link.

const EMBED_HOSTS = new Set(['www.youtube-nocookie.com', 'player.vimeo.com', 'fast.wistia.net', 'www.loom.com'])

export const VIDEO_PROVIDER_OPTIONS = [
  { value: '', label: 'Detect from link' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'vimeo', label: 'Vimeo' },
  { value: 'wistia', label: 'Wistia' },
  { value: 'loom', label: 'Loom' },
  { value: 'other', label: 'Other (link only, no embed)' },
]

const PROVIDER_LABELS = Object.fromEntries(VIDEO_PROVIDER_OPTIONS.filter((o) => o.value).map((o) => [o.value, o.label.split(' (')[0]]))

export function videoProviderLabel(provider) {
  return PROVIDER_LABELS[provider] || null
}

export function isAllowedEmbedUrl(url) {
  if (!url || typeof url !== 'string') return false
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' && EMBED_HOSTS.has(parsed.hostname) && !parsed.username && !parsed.password
  } catch {
    return false
  }
}

export const VIDEO_LESSON_TYPES = ['video', 'recording']

export function isVideoLesson(lesson) {
  return !!lesson && VIDEO_LESSON_TYPES.includes(lesson.lessonType)
}

// Mirrors backend app/services/video_embed.py _PROVIDER_HOSTS: a preview of
// what the server will detect, used only for editor guidance. The server
// stays authoritative.
const PROVIDER_HOSTS = {
  youtube: ['youtube.com', 'youtu.be', 'youtube-nocookie.com'],
  vimeo: ['vimeo.com'],
  wistia: ['wistia.com', 'wistia.net', 'wi.st'],
  loom: ['loom.com'],
}

// -> {state: 'empty'|'embed_code'|'invalid'|'embed'|'link', provider, label}
export function describeVideoLink(url) {
  const value = (url || '').trim()
  if (!value) return { state: 'empty', provider: null, label: null }
  if (/<\s*iframe|<\s*script|<\s*embed/i.test(value)) return { state: 'embed_code', provider: null, label: null }
  let parsed
  try {
    parsed = new URL(value)
  } catch {
    return { state: 'invalid', provider: null, label: null }
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || /\s/.test(value)) return { state: 'invalid', provider: null, label: null }
  const host = parsed.hostname.toLowerCase().replace(/^www\./, '')
  for (const [provider, domains] of Object.entries(PROVIDER_HOSTS)) {
    if (domains.some((d) => host === d || host.endsWith(`.${d}`))) {
      return { state: 'embed', provider, label: videoProviderLabel(provider) }
    }
  }
  return { state: 'link', provider: 'other', label: null }
}

export function videoLinkHint(url) {
  const info = describeVideoLink(url)
  if (info.state === 'embed_code') return { tone: 'error', text: 'Paste the video’s link, not its embed code. Embed code is never accepted.' }
  if (info.state === 'invalid') return { tone: 'error', text: 'Enter a full link starting with https://' }
  if (info.state === 'embed') return { tone: 'ok', text: `${info.label} link detected: it will play on the page.` }
  if (info.state === 'link') return { tone: 'info', text: 'Not a YouTube, Vimeo, Wistia or Loom link: it will open as a link on its own site rather than play on the page.' }
  return null
}

/** Whether an embedded player may be shown: only for an allowlisted player
 * URL, and only with Preferences consent or after the visitor pressed Play
 * on this video. Marketing consent is irrelevant (videos are functional
 * media, not advertising). */
export function shouldShowPlayer(embedUrl, { preferencesConsent = false, playRequested = false } = {}) {
  return isAllowedEmbedUrl(embedUrl) && (preferencesConsent || playRequested)
}
