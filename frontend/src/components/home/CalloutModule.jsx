import MediaImage from '../ui/MediaImage'
import CtaLink from '../ui/CtaLink'

/**
 * Shared rendering for the three simple CTA-style modules
 * (editorial_callout, community_cta, mentorship_cta) — same fields
 * (heading/subheading/media/CTA), just a different default destination
 * and a `tone` so Community/Mentorship read as distinct sections instead
 * of three identical-looking blocks.
 */
export default function CalloutModule({ module, defaultCtaLabel, defaultCtaUrl, tone = 'light' }) {
  if (!module.heading) return null
  const ctaLabel = module.ctaLabel || defaultCtaLabel
  const ctaUrl = module.ctaUrl || defaultCtaUrl
  const isDark = tone === 'dark'

  return (
    <section className={`border-t border-taupe-200 py-14 sm:py-16 ${isDark ? 'bg-plum-600 text-ivory' : ''}`}>
      <div className="container-editorial grid grid-cols-1 items-center gap-10 lg:grid-cols-2">
        {module.media && (
          <MediaImage
            media={module.media}
            variant="medium"
            alt={module.media.altText || module.heading}
            width={900}
            height={600}
            aspect={3 / 2}
            tone={isDark ? 'plum' : undefined}
            className="aspect-[3/2] w-full object-cover"
          />
        )}
        <div className={module.media ? '' : 'mx-auto max-w-2xl text-center'}>
          <h2 className={`font-serif text-2xl font-semibold sm:text-3xl ${isDark ? 'text-ivory' : 'text-charcoal'}`}>
            {module.heading}
          </h2>
          {module.subheading && (
            <p className={`mt-3 text-base ${isDark ? 'text-ivory/80' : 'text-charcoal-600'}`}>{module.subheading}</p>
          )}
          {ctaLabel && ctaUrl && (
            <CtaLink to={ctaUrl} className={isDark ? 'btn-outline-light mt-6 inline-flex' : 'btn-primary mt-6 inline-flex'}>
              {ctaLabel}
            </CtaLink>
          )}
        </div>
      </div>
    </section>
  )
}
