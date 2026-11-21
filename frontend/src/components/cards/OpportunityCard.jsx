import { Link } from 'react-router-dom'
import { Clock, CalendarClock } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import Tag from '../ui/Tag'
import { resolveAltText } from '../../utils/media'
import { formatFunding } from '../../utils/format'
import { closingLabel, isClosingSoon, longDate, opensLabel } from '../../utils/listingDates'

// Opportunity cards lead with the TYPE (Grant, Scholarship, Fellowship...),
// then title, provider, eligible geography, funding, and the dates that
// matter: when it opens (if upcoming) and when it closes.
export default function OpportunityCard({ opportunity }) {
  if (!opportunity) return null
  const funding = formatFunding(opportunity)
  const names = opportunity.countriesEligibleNames || []
  const geography = names.length ? (names.length > 2 ? `${names.slice(0, 2).join(', ')} +${names.length - 2}` : names.join(', ')) : opportunity.location || null
  const upcoming = opportunity.state === 'upcoming'
  const closed = opportunity.state === 'closed' || opportunity.isClosed
  const soon = !closed && !upcoming && isClosingSoon(opportunity.closing)

  return (
    <Link
      to={`/opportunities/${opportunity.slug}`}
      className="group flex overflow-hidden rounded-card flex-col justify-between border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      <div>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {opportunity.logo && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-control border border-taupe-100 bg-white p-1">
                <MediaImage
                  media={opportunity.logoMedia}
                  variant="thumbnail"
                  mediaPath={opportunity.logo}
                  alt={resolveAltText(opportunity.logoMedia, `${opportunity.organization} logo`)}
                  width={64}
                  height={64}
                  aspect={1}
                  sizes="32px"
                  className="h-full w-full object-contain"
                />
              </div>
            )}
            {opportunity.type && <Tag tone="plum">{opportunity.type}</Tag>}
          </div>
          <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
            {opportunity.accessType === 'circle_only' && (
              <span className="bg-plum-600/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-plum-700">WSF Circle</span>
            )}
            {opportunity.featured && (
              <span className="bg-burgundy-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</span>
            )}
            {opportunity.sponsored && (
              <span className="bg-taupe-200 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">Sponsored</span>
            )}
          </div>
        </div>
        <h3 className="mt-3 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {opportunity.title}
        </h3>
        {opportunity.organization && <p className="mt-1 text-sm font-medium text-charcoal-600">{opportunity.organization}</p>}
        {geography && <p className="mt-2 text-xs text-charcoal-600">Eligible: {geography}</p>}
        {funding && <p className="mt-1 text-xs font-semibold text-charcoal">{funding}</p>}
        {opportunity.shortDescription && <p className="mt-2 line-clamp-2 text-sm text-charcoal-600">{opportunity.shortDescription}</p>}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-taupe-100 pt-3 text-xs text-charcoal-600">
        {closed ? (
          <span className="font-semibold">Applications closed</span>
        ) : upcoming ? (
          <>
            <span className="inline-flex items-center gap-1 font-semibold text-plum-700">
              <CalendarClock size={12} aria-hidden="true" /> {opensLabel(opportunity.openingDate)}
            </span>
            {opportunity.closesOn && <span>Closes {longDate(opportunity.closesOn)}</span>}
          </>
        ) : opportunity.closing ? (
          <>
            <span className={`inline-flex items-center gap-1 ${soon ? 'font-semibold text-burgundy-700' : ''}`}>
              <Clock size={12} aria-hidden="true" /> {closingLabel(opportunity.closing)}
            </span>
            {soon && (
              <span className="rounded-control bg-burgundy-500/10 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-burgundy-700">Closing soon</span>
            )}
          </>
        ) : (
          <span>No closing date</span>
        )}
      </div>
    </Link>
  )
}
