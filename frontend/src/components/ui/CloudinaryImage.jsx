import { resolveImage, resolveSrcSet } from '../../utils/media'

/**
 * Responsive, layout-shift-safe image. `publicId` is a stable media
 * reference (a Cloudinary public_id in production). Always renders explicit
 * width/height so the browser reserves space before the image loads.
 */
export default function CloudinaryImage({
  publicId,
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
      src={resolveImage(publicId, { width, height: computedHeight, tone })}
      srcSet={resolveSrcSet(publicId, { aspect: ratio, tone })}
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
