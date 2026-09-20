// Image resolution layer.
//
// In production this module resolves a Cloudinary `publicId` into a responsive,
// WebP-delivered URL (f_auto,q_auto, width-based transformations, focal-point
// cropping via g_auto:<focus>). Every image-consuming component in this app
// calls `resolveImage()` / uses `<CloudinaryImage>` rather than building URLs
// itself, so pointing this at a real Cloudinary cloud name later is a one-file
// change with no UI rewrite.
//
// This offline prototype has no outbound access to a media CDN, so it renders
// deterministic, on-brand abstract-editorial placeholders instead of photography.
// The `publicId`/caption/credit/focal metadata is real and already modeled on
// every content type — swapping in photography is just changing this function.

const CLOUD_NAME = import.meta.env.VITE_CLOUDINARY_CLOUD_NAME || null

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

/**
 * Resolve a media reference to a displayable URL.
 * @param {string} publicId - stable identifier (Cloudinary public_id in production)
 * @param {object} opts - { width, height, tone, crop }
 */
export function resolveImage(publicId, opts = {}) {
  const { width = 1200, height = 800 } = opts
  if (CLOUD_NAME) {
    // Real Cloudinary delivery: automatic format (WebP where supported),
    // automatic quality, width-capped, gravity-auto cropping.
    return `https://res.cloudinary.com/${CLOUD_NAME}/image/upload/f_auto,q_auto,c_fill,g_auto,w_${width},h_${height}/${publicId}`
  }
  return svgPlaceholder(publicId, { width, height, tone: opts.tone })
}

export function resolveSrcSet(publicId, { widths = [480, 768, 1024, 1600], aspect = 1.5, tone } = {}) {
  return widths
    .map((w) => `${resolveImage(publicId, { width: w, height: Math.round(w / aspect), tone })} ${w}w`)
    .join(', ')
}
