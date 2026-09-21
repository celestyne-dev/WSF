import { resolveImage, resolveSrcSet, resolveMediaImage } from '../../utils/media'

/**
 * Responsive, layout-shift-safe image. Always renders explicit width/height
 * so the browser reserves space before the image loads.
 *
 * Two ways to call it:
 *  - `media` (+ optional `variant`, default "card") — the normalized media
 *    reference every api/*.js mapper produces for a nested Article.hero_media
 *    /Person|Author.photo/Organization|Job|Opportunity.logo/Event|Resource|
 *    Product|Series.cover_media field (see utils/media.js:mapMediaRef), or
 *    the fuller shape api/media.js's fetchMediaLibrary()/uploadMedia() etc.
 *    return. Prefers the requested generated WebP variant
 *    (thumbnail/card/medium/large/hero) and builds a real responsive srcSet
 *    from whichever variants exist, falling back to the original file only
 *    when no variants are available.
 *  - `mediaPath` — a bare path/URL, for call sites that don't have a full
 *    media object (mock-mode synthetic placeholders, or a stable identifier
 *    with no richer metadata).
 */
export default function MediaImage({
  media,
  variant = 'card',
  mediaPath,
  alt,
  width = 1200,
  height = 800,
  aspect,
  sizes,
  tone,
  className = '',
  priority = false,
}) {
  const ratio = aspect || width / height
  const computedHeight = Math.round(width / ratio)
  const resolvedAlt = alt ?? media?.altText ?? ''
  // A caller-supplied `sizes` always wins. Otherwise: `priority` marks a
  // hero/LCP image that genuinely spans (close to) the viewport, so 100vw
  // is correct there; every other call site already passes a `width` that
  // reflects its actual rendered box (a card, an avatar, a logo), so
  // defaulting to that instead of 100vw stops the srcSet negotiation from
  // fetching the largest generated variant for a small thumbnail just
  // because nothing told the browser it wasn't full-width.
  const resolvedSizes = sizes || (priority ? '100vw' : `${width}px`)

  const { src, srcSet } = media
    ? resolveMediaImage(media, { variant, width, height: computedHeight, aspect: ratio, tone })
    : {
        src: resolveImage(mediaPath, { width, height: computedHeight, tone }),
        srcSet: resolveSrcSet(mediaPath, { aspect: ratio, tone }),
      }

  return (
    <img
      src={src}
      srcSet={srcSet}
      sizes={resolvedSizes}
      alt={resolvedAlt}
      width={width}
      height={computedHeight}
      loading={priority ? 'eager' : 'lazy'}
      decoding="async"
      className={className}
    />
  )
}
