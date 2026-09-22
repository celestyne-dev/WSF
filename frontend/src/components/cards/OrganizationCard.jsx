import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'

const TYPE_LABELS = {
  company: 'Company',
  nonprofit: 'Nonprofit',
  foundation: 'Foundation',
  government: 'Government',
  educational_institution: 'Educational institution',
  media_organization: 'Media organization',
  professional_association: 'Professional association',
  social_enterprise: 'Social enterprise',
  community_organization: 'Community organization',
  other: 'Other',
}

// `organization` must be a normalized object from api/taxonomies.js — its
// `country` field is already resolved there. No lookup here.
export default function OrganizationCard({ organization }) {
  if (!organization) return null
  const metaLine = [TYPE_LABELS[organization.type], organization.country?.name || organization.countryCode].filter(Boolean).join(' · ')
  return (
    <Link
      to={`/organizations/${organization.slug}`}
      className="group flex items-center gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      {organization.logo ? (
        <div className="flex h-16 w-16 shrink-0 items-center justify-center border border-taupe-100 bg-white p-2">
          <MediaImage
            media={organization.logoMedia}
            variant="thumbnail"
            mediaPath={organization.logo}
            alt={`${organization.name} logo`}
            width={112}
            height={112}
            aspect={1}
            className="h-full w-full object-contain"
          />
        </div>
      ) : (
        <div className="flex h-16 w-16 shrink-0 items-center justify-center border border-taupe-100 bg-taupe-100 font-serif text-lg font-semibold text-charcoal-600">
          {organization.name?.[0]}
        </div>
      )}
      <div className="min-w-0">
        <h3 className="font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">
          {organization.name}
        </h3>
        {metaLine && <p className="text-sm text-charcoal-600">{metaLine}</p>}
        {organization.shortDescription && <p className="mt-1 line-clamp-1 text-sm text-charcoal-600">{organization.shortDescription}</p>}
      </div>
    </Link>
  )
}
