import { Link } from 'react-router-dom'
import { Infinity as InfinityIcon } from 'lucide-react'
import useLifetimeOffer from '../../hooks/useLifetimeOffer'

// A quiet, recurring membership value signal on eligible premium content.
// Lifetime member -> "Included with your Lifetime membership" (server label).
// Anyone else -> "Included with WSF Lifetime · Learn more", only while a
// Lifetime plan is actually on sale. Display only: access is server-side.
export default function LifetimeValueNote({ included, viewerLabel, className = '' }) {
  const isLifetimeMember = typeof viewerLabel === 'string' && /lifetime/i.test(viewerLabel)
  const { available } = useLifetimeOffer(included && !isLifetimeMember)
  if (!included) return null
  if (isLifetimeMember) {
    return (
      <p className={`inline-flex items-center gap-2 text-sm font-semibold text-plum-600 ${className}`}>
        <InfinityIcon size={16} aria-hidden="true" /> {viewerLabel}
      </p>
    )
  }
  if (!available) return null
  return (
    <p className={`inline-flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-charcoal-600 ${className}`}>
      <InfinityIcon size={16} aria-hidden="true" className="text-plum-600" />
      <span className="font-semibold text-plum-600">Included with WSF Lifetime</span>
      <Link to="/lifetime" className="font-semibold text-burgundy-600 hover:underline">
        Learn more <span aria-hidden="true">→</span>
      </Link>
    </p>
  )
}
