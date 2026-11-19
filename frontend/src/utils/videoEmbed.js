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
