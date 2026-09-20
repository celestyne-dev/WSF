import { getOrganizationBySlug } from '../../mock/organizations'
import MediaImage from '../ui/MediaImage'

export default function PartnersModule({ module }) {
  const partners = (module.partnerSlugs || []).map((s) => getOrganizationBySlug(s)).filter(Boolean)
  if (!partners.length) return null

  return (
    <section className="py-12">
      <div className="container-editorial">
        <p className="text-center text-xs font-semibold uppercase tracking-widest2 text-charcoal-600">{module.heading}</p>
        <div className="mt-6 grid grid-cols-2 items-center gap-8 sm:grid-cols-4">
          {partners.map((p) => (
            <MediaImage
              key={p.id}
              mediaPath={p.logo}
              alt={p.name}
              width={200}
              height={100}
              aspect={2}
              tone="taupe"
              className="mx-auto h-12 w-auto grayscale transition-all hover:grayscale-0"
            />
          ))}
        </div>
      </div>
    </section>
  )
}
