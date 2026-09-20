import { resolveImage, resolveSrcSet } from '../../utils/media'

/**
 * Responsive, layout-shift-safe image. `mediaPath` is a stable media
 * reference — in production, the path a Flask-processed upload is stored
 * and served at under the Hostinger VPS `/media/` root (see
 * src/utils/media.js). Always renders explicit width/height so the browser
 * reserves space before the image loads.
 */
export default function MediaImage({
  mediaPath,
  alt,
  width = 1200,
  height = 800,
  aspect,
  sizes = '100vw',
  tone,
  className = '',
  priority = false,
}) {
  const ratio = aspect || width / height
  const computedHeight = Math.round(width / ratio)

  return (
    <img
      src={resolveImage(mediaPath, { width, height: computedHeight, tone })}
      srcSet={resolveSrcSet(mediaPath, { aspect: ratio, tone })}
      sizes={sizes}
      alt={alt || ''}
      width={width}
      height={computedHeight}
      loading={priority ? 'eager' : 'lazy'}
      decoding="async"
      className={className}
    />
  )
}
