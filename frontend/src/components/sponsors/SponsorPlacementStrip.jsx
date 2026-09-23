import { useEffect, useRef, useState } from 'react'
import { fetchPublicSponsorPlacements } from '../../api/sponsors'
import { trackEvent } from '../../utils/analytics'
import MediaImage from '../ui/MediaImage'

/**
 * One consistent presentation for a disclosed sponsor placement — logo (or
 * a tasteful text fallback, never a broken image), disclosure label,
 * sponsor name, and an optional CTA. Used for every public placement key
 * (homepage strip, article sidebar/inline) so disclosure logic never has
 * to be reimplemented per page.
 *
 * Impressions/clicks are tracked via the existing generic analytics
 * pipeline (trackEvent -> POST /analytics/events), tagged with
 * entityType "Sponsor" — no separate analytics system. Each sponsor's
 * impression fires once per mount (a ref-tracked set), not on every
 * re-render.
 */
export default function SponsorPlacementStrip({ placementKey, heading, className = '', layout = 'grid' }) {
  const [sponsors, setSponsors] = useState([])
  const trackedImpressions = useRef(new Set())

  useEffect(() => {
    let active = true
    fetchPublicSponsorPlacements(placementKey)
      .then((rows) => active && setSponsors(rows))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [placementKey])

  useEffect(() => {
    sponsors.forEach((s) => {
      if (trackedImpressions.current.has(s.id)) return
      trackedImpressions.current.add(s.id)
      trackEvent('sponsor_impression', { placement: placementKey }, { entityType: 'Sponsor', entityId: String(s.id) })
    })
  }, [sponsors, placementKey])

  if (sponsors.length === 0) return null

  const isGrid = layout === 'grid'

  return (
    <section className={`${isGrid ? 'py-10' : ''} ${className}`}>
      <div className={isGrid ? 'container-editorial' : ''}>
        {heading && <p className="mb-4 text-center text-xs font-semibold uppercase tracking-widest2 text-charcoal-600">{heading}</p>}
        <div className={isGrid ? 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3' : 'space-y-4'}>
          {sponsors.map((sponsor) => (
            <SponsorCard key={sponsor.id} sponsor={sponsor} placementKey={placementKey} />
          ))}
        </div>
      </div>
    </section>
  )
}

function SponsorCard({ sponsor, placementKey }) {
  const logo = sponsor.logo || sponsor.organization?.logo
  const validUrl = sponsor.sponsorUrl && /^https?:\/\//i.test(sponsor.sponsorUrl) ? sponsor.sponsorUrl : null

  function handleClick() {
    trackEvent('sponsor_click', { placement: placementKey }, { entityType: 'Sponsor', entityId: String(sponsor.id) })
  }

  return (
    <div className="flex items-start gap-3 border border-taupe-200 bg-white p-4">
      <div className="flex h-12 w-16 shrink-0 items-center justify-center overflow-hidden bg-taupe-100">
        {logo?.mediaPath ? (
          <MediaImage media={logo} variant="thumbnail" width={160} height={100} aspect={16 / 10} alt={logo.altText || sponsor.publicName} className="h-full w-full object-contain" />
        ) : (
          <span className="px-1 text-center text-[10px] font-semibold uppercase tracking-wide text-charcoal-600/60">{sponsor.publicName}</span>
        )}
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-burgundy-600">{sponsor.disclosureLabel}</p>
        <p className="truncate text-sm font-semibold text-charcoal">{sponsor.publicName}</p>
        {sponsor.publicDescription && <p className="mt-0.5 line-clamp-2 text-xs text-charcoal-600">{sponsor.publicDescription}</p>}
        {validUrl && (
          <a href={validUrl} target="_blank" rel="noopener noreferrer sponsored" onClick={handleClick} className="mt-1 inline-block text-xs font-semibold text-burgundy-600 hover:underline">
            {sponsor.ctaLabel || 'Learn more'}
          </a>
        )}
      </div>
    </div>
  )
}
