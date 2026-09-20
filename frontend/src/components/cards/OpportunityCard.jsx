import { Link } from 'react-router-dom'
import { formatDeadline } from '../../utils/format'
import Tag from '../ui/Tag'

export default function OpportunityCard({ opportunity }) {
  if (!opportunity) return null
  return (
    <Link
      to={`/opportunities/${opportunity.slug}`}
      className="group flex flex-col justify-between border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      <div>
        <div className="flex items-center justify-between gap-3">
          <Tag tone="plum">{opportunity.type}</Tag>
          {opportunity.sponsored && <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">Sponsored</span>}
        </div>
        <h3 className="mt-3 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {opportunity.title}
        </h3>
        <p className="mt-1 text-sm font-medium text-charcoal-600">{opportunity.organization}</p>
        <p className="mt-2 line-clamp-2 text-sm text-charcoal-600">{opportunity.description}</p>
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-taupe-100 pt-3 text-xs text-charcoal-600">
        <span>{opportunity.fundingValue}</span>
        <span className="font-semibold text-burgundy-600">{formatDeadline(opportunity.deadline)}</span>
      </div>
    </Link>
  )
}
