import { Link } from 'react-router-dom'
import { Lock } from 'lucide-react'
import CloudinaryImage from '../ui/CloudinaryImage'
import { formatCurrency } from '../../utils/format'

export default function ResourceCard({ resource }) {
  if (!resource) return null
  return (
    <Link to={`/resources/${resource.slug}`} className="group block">
      <div className="relative overflow-hidden">
        <CloudinaryImage
          publicId={resource.coverImage}
          alt={resource.name}
          width={800}
          height={560}
          aspect={10 / 7}
          className="aspect-[10/7] w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        {resource.isPremium && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1 bg-charcoal/85 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-ivory">
            <Lock size={11} /> Premium
          </span>
        )}
      </div>
      <div className="mt-3">
        <span className="eyebrow">{resource.type}</span>
        <h3 className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {resource.name}
        </h3>
        <p className="mt-1 text-sm font-medium text-charcoal-600">{resource.isPremium ? formatCurrency(resource.price, resource.currency) : 'Free download'}</p>
      </div>
    </Link>
  )
}
