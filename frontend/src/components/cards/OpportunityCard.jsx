import { Link } from 'react-router-dom'
import { Clock } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import Tag from '../ui/Tag'
import { formatDeadline, formatFunding } from '../../utils/format'

export default function OpportunityCard({ opportunity }) {
  if (!opportunity) return null
  const funding = formatFunding(opportunity)
  const geography = opportunity.countriesEligibleNames?.length
    ? opportunity.countriesEligibleNames.length > 2
      ? `${opportunity.countriesEligibleNames.slice(0, 2).join(', ')} +${opportunity.countriesEligibleNames.length - 2}`
      : opportunity.countriesEligibleNames.join(', ')
    : null

  return (
    <Link
      to={`/opportunities/${opportunity.slug}`}
      className="group flex flex-col justify-between border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      <div>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {opportunity.logo && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-taupe-100 bg-white p-1">
                <MediaImage
                  media={opportunity.logoMedia}
                  variant="thumbnail"
                  mediaPath={opportunity.logo}
                  alt={opportunity.organization}
                  width={64}
                  height={64}
                  aspect={1}
                  className="h-full w-full object-contain"
                />
              </div>
            )}
            {opportunity.type && <Tag tone="plum">{opportunity.type}</Tag>}
          </div>
          <div className="flex shrink-0 gap-1.5">
            {opportunity.featured && (
              <span className="bg-burgundy-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">
                Featured
              </span>
            )}
            {opportunity.sponsored && (
              <span className="bg-taupe-200 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">
                Sponsored
              </span>
            )}
          </div>
        </div>
        <h3 className="mt-3 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {opportunity.title}
        </h3>
        {opportunity.organization && <p className="mt-1 text-sm font-medium text-charcoal-600">{opportunity.organization}</p>}
        {opportunity.shortDescription && <p className="mt-2 line-clamp-2 text-sm text-charcoal-600">{opportunity.shortDescription}</p>}
        {geography && <p className="mt-2 text-xs text-charcoal-600">{geography}</p>}
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-taupe-100 pt-3 text-xs text-charcoal-600">
        <span>{funding || ''}</span>
        {opportunity.isClosed ? (
          <span className="font-semibold text-charcoal-600/70">Applications closed</span>
        ) : opportunity.deadline ? (
          <span className="inline-flex items-center gap-1 font-semibold text-burgundy-600">
            <Clock size={12} /> {formatDeadline(opportunity.deadline)}
          </span>
        ) : null}
      </div>
    </Link>
  )
}
