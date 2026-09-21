import { useEffect, useState } from 'react'
import { fetchOrganizationBySlug } from '../../api/taxonomies'
import MediaImage from '../ui/MediaImage'

export default function PartnersModule({ module }) {
  const [partners, setPartners] = useState([])

  useEffect(() => {
    let active = true
    Promise.all((module.partnerSlugs || []).map((s) => fetchOrganizationBySlug(s).catch(() => null)))
      .then((orgs) => active && setPartners(orgs.filter(Boolean)))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [module.partnerSlugs])

  if (!partners.length) return null

  return (
    <section className="py-12">
      <div className="container-editorial">
        <p className="text-center text-xs font-semibold uppercase tracking-widest2 text-charcoal-600">{module.heading}</p>
        <div className="mt-6 grid grid-cols-2 items-center gap-8 sm:grid-cols-4">
          {partners.map((p) => (
            <MediaImage
              key={p.id}
              media={p.logoMedia}
              variant="thumbnail"
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
