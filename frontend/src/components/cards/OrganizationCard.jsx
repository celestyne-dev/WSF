import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'

export default function OrganizationCard({ organization }) {
  if (!organization) return null
  return (
    <Link
      to={`/organizations/${organization.slug}`}
      className="group flex items-center gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      <MediaImage
        mediaPath={organization.logo}
        alt={`${organization.name} logo`}
        width={112}
        height={112}
        aspect={1}
        className="h-16 w-16 shrink-0 border border-taupe-100 object-cover"
      />
      <div className="min-w-0">
        <h3 className="font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">
          {organization.name}
        </h3>
        <p className="text-sm text-charcoal-600">
          {organization.industry} &middot; {organization.country}
        </p>
        <p className="mt-1 line-clamp-1 text-sm text-charcoal-600">{organization.description}</p>
      </div>
    </Link>
  )
}
