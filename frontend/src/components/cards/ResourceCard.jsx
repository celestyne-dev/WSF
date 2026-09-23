import { Link } from 'react-router-dom'
import { Mail, Lock, ExternalLink } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { formatCurrency } from '../../utils/format'

const ACCESS_BADGE = {
  email_gate: { icon: Mail, label: 'Free — email required' },
  premium: { icon: Lock, label: 'Premium' },
  member_only: { icon: Lock, label: 'Members only' },
  external_link: { icon: ExternalLink, label: 'External' },
}

export default function ResourceCard({ resource }) {
  if (!resource) return null
  const badge = ACCESS_BADGE[resource.accessType]
  return (
    <Link to={`/resources/${resource.slug}`} className="group block">
      <div className="relative overflow-hidden bg-taupe-100">
        <MediaImage
          media={resource.coverMedia}
          variant="card"
          mediaPath={resource.coverImage}
          alt={resource.name}
          width={800}
          height={1000}
          aspect={4 / 5}
          className="aspect-[4/5] w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        {resource.featured && (
          <span className="absolute left-3 top-3 bg-burgundy-600 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>
        )}
        {badge && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1 bg-charcoal/85 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-ivory">
            <badge.icon size={11} /> {badge.label}
          </span>
        )}
      </div>
      <div className="mt-3">
        <span className="eyebrow">{resource.type}</span>
        <h3 className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {resource.name}
        </h3>
        {resource.shortDescription && <p className="mt-1 line-clamp-2 text-sm text-charcoal-600/80">{resource.shortDescription}</p>}
        <div className="mt-1.5 flex items-center gap-2 text-sm font-medium text-charcoal-600">
          {resource.author?.name && <span>{resource.author.name}</span>}
          {resource.author?.name && <span className="text-charcoal-600/40">·</span>}
          <span>{resource.isFree ? 'Free' : formatCurrency(resource.price, resource.currency)}</span>
        </div>
      </div>
    </Link>
  )
}
