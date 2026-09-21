// Image resolution layer.
//
// In production, media is uploaded through the CMS to the Flask backend,
// which validates, processes (Pillow), and stores it on the Hostinger VPS
// filesystem outside the frontend source tree (e.g.
// /var/www/womenshapingfutures/media/articles/...). Flask persists the
// resulting metadata (Media model: uuid, stored_filename, file_path,
// public_url, width, height, alt_text, caption, credit, ...) and Nginx
// serves the optimized WebP files directly under a clean public path such
// as https://womenshapingfutures.org/media/articles/example-image.webp —
// Flask itself is only in the upload/validate/process/authorize path, never
// in the hot path of serving an image to a visitor.
//
// Every image-consuming component in this app calls `resolveImage()` /
// `resolveSrcSet()` (via `<MediaImage>`) rather than building a URL itself,
// and passes a stable `mediaPath` — the same reference the API will one day
// return as `public_url` (minus variant/extension). That keeps this file as
// the single place that knows how to turn a media reference into a URL, so
// pointing the app at the real backend is a one-file change with no
// component rewrites.
//
// Multiple responsive variants (thumbnail/card/medium/large/hero) are
// generated server-side in production; `resolveImage` picks the closest
// variant for the requested width so a small card never downloads a
// full-resolution hero image.
//
// This offline prototype has no media backend to call, so it renders
// deterministic, on-brand abstract-editorial placeholders instead of real
// photography. The `mediaPath`/caption/credit metadata is real and already
// modeled on every content type — swapping in real uploads later is just
// changing the implementation of `resolveImage`/`resolveSrcSet` below.

const MEDIA_BASE_URL = import.meta.env.VITE_MEDIA_BASE_URL || null

// The backend's `media.public_url` is root-relative (e.g.
// "/media/originals/{uuid}.webp" — see backend/app/services/media.py, built
// from the MEDIA_URL config value, typically "/media/"), not a full URL.
// That's correct when the frontend and API share an origin (Nginx serving
// both in production), but in local dev the API runs on a different port
// (VITE_API_URL=http://localhost:5000/api/v1) than the Vite dev server
// (5173) — a root-relative path would otherwise resolve against the wrong
// origin. Deriving the API's origin once here, from whichever form
// VITE_API_URL takes, keeps every image request pointed at the server that
// actually has the file.
function resolveApiOrigin() {
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  try {
    return new URL(apiUrl, window.location.origin).origin
  } catch {
    return ''
  }
}

const API_ORIGIN = resolveApiOrigin()

// Mirrors the responsive variants the Flask media service generates on
// upload (see backend/app/services/media.py). Width is each variant's
// target max dimension; `resolveImage` snaps to the closest one at or
// above the requested width so callers never pay for more pixels than a
// slot needs.
const MEDIA_VARIANTS = [
  { name: 'thumbnail', width: 320 },
  { name: 'card', width: 640 },
  { name: 'medium', width: 960 },
  { name: 'large', width: 1280 },
  { name: 'hero', width: 1920 },
]

function pickVariant(targetWidth) {
  const fit = MEDIA_VARIANTS.find((v) => v.width >= targetWidth)
  return fit || MEDIA_VARIANTS[MEDIA_VARIANTS.length - 1]
}

const TONES = {
  blush: ['#F9E4DD', '#E3AFA0', '#93504A'],
  plum: ['#EDE3E8', '#5B3A4E', '#33202C'],
  burgundy: ['#F1E3E0', '#7A2438', '#4A1220'],
  taupe: ['#F5EEE4', '#BFB1A0', '#6B5D4C'],
  ink: ['#EDE7DE', '#3A3335', '#171315'],
}

const TONE_KEYS = Object.keys(TONES)

function hashSeed(seed) {
  let h = 0
  const str = String(seed)
  for (let i = 0; i < str.length; i += 1) {
    h = (h * 31 + str.charCodeAt(i)) >>> 0
  }
  return h
}

function svgPlaceholder(seed, { width = 1200, height = 800, tone } = {}) {
  const h = hashSeed(seed)
  const chosenTone = tone && TONES[tone] ? tone : TONE_KEYS[h % TONE_KEYS.length]
  const [c1, c2, c3] = TONES[chosenTone]
  const angle = h % 360
  const cx = 15 + (h % 55)
  const cy = 15 + ((h >> 3) % 55)
  const r = 38 + (h % 26)
  const cx2 = 100 - cx
  const cy2 = 100 - cy
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 100 ${(100 * height) / width}">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%" gradientTransform="rotate(${angle} 50 50)">
      <stop offset="0%" stop-color="${c1}"/>
      <stop offset="100%" stop-color="${c2}"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <circle cx="${cx}%" cy="${cy}%" r="${r}%" fill="${c3}" fill-opacity="0.16"/>
  <circle cx="${cx2}%" cy="${cy2}%" r="${r * 0.55}%" fill="${c3}" fill-opacity="0.12"/>
</svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

// A real upload's `mediaPath` is the backend's `media.public_url` — either
// root-relative ("/media/originals/{uuid}.webp") or, if MEDIA_URL is
// configured as a full origin, already absolute — never a bare path to
// suffix a variant onto. Mock mode's `mediaPath` is a short synthetic key
// like "articles/my-hero" with no real file behind it and no leading slash,
// which is what the `-{variant}.webp` convention below and the SVG
// placeholder fallback exist for. Recognizing a real backend path (either
// form) keeps both call shapes correct through one function without every
// caller needing to know which mode is active.
function isBackendMediaPath(value) {
  return typeof value === 'string' && (/^https?:\/\//i.test(value) || value.startsWith('/'))
}

function toAbsoluteUrl(value) {
  if (/^https?:\/\//i.test(value)) return value
  return `${API_ORIGIN}${value}`
}

/**
 * Resolve a media reference to a displayable URL.
 * @param {string} mediaPath - either a real upload's public_url (root-
 *   relative or absolute), or (mock mode only) a stable synthetic
 *   identifier like "articles/my-hero".
 * @param {object} opts - { width, height, tone }
 */
export function resolveImage(mediaPath, opts = {}) {
  const { width = 1200, height = 800 } = opts
  if (!mediaPath) return svgPlaceholder('placeholder', { width, height, tone: opts.tone })
  if (isBackendMediaPath(mediaPath)) return toAbsoluteUrl(mediaPath)
  if (MEDIA_BASE_URL) {
    // Real deployment: Nginx serves the pre-generated WebP variant directly
    // from the Hostinger VPS filesystem — Flask is not in this request path.
    const variant = pickVariant(width)
    return `${MEDIA_BASE_URL}/${mediaPath}-${variant.name}.webp`
  }
  return svgPlaceholder(mediaPath, { width, height, tone: opts.tone })
}

export function resolveSrcSet(mediaPath, { widths = [480, 768, 1024, 1600], aspect = 1.5, tone } = {}) {
  // A real upload's public_url is one fixed file — there's no synthetic
  // variant set to build a srcSet from, so omit the attribute and let the
  // browser use `src` as-is (see MediaImage.jsx).
  if (isBackendMediaPath(mediaPath)) return undefined
  return widths
    .map((w) => `${resolveImage(mediaPath, { width: w, height: Math.round(w / aspect), tone })} ${w}w`)
    .join(', ')
}
