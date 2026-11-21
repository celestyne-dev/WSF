import CtaLink from '../ui/CtaLink'

// The homepage mission statement: every word is CMS-editable (heading,
// subheading, supporting copy, CTA); nothing is hardcoded here.
export default function MissionModule({ module }) {
  if (!module.heading) return null
  const paragraphs = (module.body || '').split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)
  return (
    <section className="border-t border-taupe-200 bg-ivory py-16 sm:py-20">
      <div className="container-editorial">
        <div className="mx-auto max-w-3xl text-center">
          {module.eyebrow && <p className="eyebrow">{module.eyebrow}</p>}
          <h2 className="mt-3 font-serif text-3xl font-semibold leading-tight text-charcoal sm:text-4xl">{module.heading}</h2>
          {module.subheading && <p className="mt-4 text-lg text-charcoal-600">{module.subheading}</p>}
          {paragraphs.map((p, i) => (
            <p key={i} className="mt-4 text-base leading-relaxed text-charcoal-600">
              {p}
            </p>
          ))}
          {module.ctaLabel && module.ctaUrl && (
            <CtaLink to={module.ctaUrl} className="btn-outline mt-8 inline-flex">
              {module.ctaLabel}
            </CtaLink>
          )}
        </div>
      </div>
    </section>
  )
}
