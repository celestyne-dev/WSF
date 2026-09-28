import { Link } from 'react-router-dom'
import { ShieldCheck, Star } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { DIRECTORY_OWNERSHIP_LABELS } from '../../constants/directory'

// `listing` must be a normalized object from api/directory.js
// (mapDirectoryListingPublic) — country/logo are already resolved there.
export default function DirectoryCard({ listing }) {
  if (!listing?.organization) return null
  const org = listing.organization
  const categoryLine = listing.categories?.map((c) => c.name).join(', ')
  const locationLine = [org.location, org.country?.name].filter(Boolean).join(', ')
  const showClassification = listing.ownershipClassification && listing.ownershipClassification !== 'unspecified'

  return (
    <Link
      to={`/directory/${org.slug}`}
      className="group flex flex-col gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      <div className="flex items-start gap-4">
        {org.logo ? (
          <div className="flex h-14 w-14 shrink-0 items-center justify-center border border-taupe-100 bg-white p-2">
            <MediaImage media={org.logo} variant="thumbnail" alt={`${org.name} logo`} width={112} height={112} aspect={1} className="h-full w-full object-contain" />
          </div>
        ) : (
          <div className="flex h-14 w-14 shrink-0 items-center justify-center border border-taupe-100 bg-taupe-100 font-serif text-base font-semibold text-charcoal-600">
            {org.name?.[0]}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">{org.name}</h3>
            {listing.isCurrentlyFeatured && (
              <span className="inline-flex shrink-0 items-center gap-1 bg-burgundy-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-burgundy-700">
                <Star size={10} fill="currentColor" /> Featured
              </span>
            )}
          </div>
          {(categoryLine || locationLine) && (
            <p className="text-sm text-charcoal-600">{[categoryLine, locationLine].filter(Boolean).join(' · ')}</p>
          )}
        </div>
      </div>

      {(listing.serviceSummary || org.shortDescription) && (
        <p className="line-clamp-2 text-sm text-charcoal-600">{listing.serviceSummary || org.shortDescription}</p>
      )}

      {(showClassification || listing.verificationStatus === 'verified') && (
        <div className="flex flex-wrap items-center gap-2">
          {showClassification && (
            <span className="bg-taupe-100 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">
              {DIRECTORY_OWNERSHIP_LABELS[listing.ownershipClassification]}
              {listing.classificationProvenance === 'self_attested' ? ' — self-attested' : ''}
            </span>
          )}
          {listing.verificationStatus === 'verified' && (
            <span className="inline-flex items-center gap-1 bg-emerald-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
              <ShieldCheck size={12} /> Verified by WSF
            </span>
          )}
        </div>
      )}
    </Link>
  )
}
