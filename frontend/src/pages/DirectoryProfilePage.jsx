import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Globe, ShieldCheck, Star, ArrowUpRight } from 'lucide-react'
import { fetchDirectoryListing } from '../api/directory'
import { fetchJobs } from '../api/jobs'
import { resolveImage } from '../utils/media'
import {
  DIRECTORY_OWNERSHIP_LABELS,
  DIRECTORY_LISTING_TYPE_LABELS,
  DIRECTORY_SERVICE_MODE_LABELS,
  DIRECTORY_VERIFIED_EXPLANATION,
} from '../constants/directory'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import JobCard from '../components/cards/JobCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

// Minimal schema.org Organization structured data, built only from real
// fields — never LocalBusiness (this directory is global, not tied to a
// single physical location) and never inferred facts.
function useDirectoryStructuredData(listing, canonicalUrl) {
  useEffect(() => {
    if (!listing) return
    const org = listing.organization
    const data = {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: org.name,
      url: canonicalUrl,
      ...(org.website ? { sameAs: [org.website] } : {}),
      ...(org.logo ? { logo: resolveImage(org.logo, { width: 400, height: 400 }) } : {}),
      ...(org.foundedYear ? { foundingDate: String(org.foundedYear) } : {}),
      ...(listing.serviceSummary ? { description: listing.serviceSummary } : {}),
    }
    let el = document.head.querySelector('script[data-directory-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-directory-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [listing, canonicalUrl])
}

export default function DirectoryProfilePage() {
  const { slug } = useParams()
  const [listing, setListing] = useState(undefined)
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setListing(undefined)
    setJobs([])
    setError(null)

    fetchDirectoryListing(slug)
      .then((data) => {
        if (!active) return
        setListing(data)
        if (!data) return
        fetchJobs({ organization: slug, pageSize: 10 })
          .then((res) => active && setJobs(res.items))
          .catch(() => {})
      })
      .catch(() => active && setError('Something went wrong loading this listing. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = `https://womenshapingfutures.org/directory/${slug}`

  useSeo(
    listing
      ? {
          title: listing.seo?.title || `${listing.organization.name} | Business & Professional Directory | Women Shaping Futures`,
          description: listing.seo?.description || listing.serviceSummary || listing.organization.shortDescription,
          canonical: listing.seo?.canonical || canonicalUrl,
          image: listing.organization.logo ? resolveImage(listing.organization.logo, { width: 1200, height: 630 }) : undefined,
          robots: listing.seo?.robots,
        }
      : {},
  )

  useDirectoryStructuredData(listing, canonicalUrl)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this listing" description={error} /></div>
  if (listing === undefined) return <PageLoader />
  if (listing === null) return <NotFoundPage />

  const org = listing.organization
  const showClassification = listing.ownershipClassification && listing.ownershipClassification !== 'unspecified'
  const metaLine = [DIRECTORY_LISTING_TYPE_LABELS[listing.listingType], org.industry, [org.location, org.country?.name].filter(Boolean).join(', ')]
    .filter(Boolean)
    .join(' · ')

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Directory', to: '/directory' }, { label: org.name }]} />
          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            {org.logo ? (
              <div className="flex h-24 w-24 shrink-0 items-center justify-center border border-taupe-200 bg-white p-3">
                <MediaImage media={org.logo} variant="thumbnail" alt={`${org.name} logo`} width={200} height={200} aspect={1} className="h-full w-full object-contain" />
              </div>
            ) : null}
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{org.name}</h1>
                {listing.isCurrentlyFeatured && (
                  <span className="inline-flex items-center gap-1 bg-burgundy-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-burgundy-700">
                    <Star size={11} fill="currentColor" /> Featured
                  </span>
                )}
              </div>
              {metaLine && <p className="mt-1 text-base text-charcoal-600">{metaLine}</p>}
              {org.website && (
                <a href={org.website} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-burgundy-600 hover:underline">
                  <Globe size={14} /> Visit website
                </a>
              )}
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {showClassification && (
              <span className="bg-taupe-100 px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                {DIRECTORY_OWNERSHIP_LABELS[listing.ownershipClassification]}
                {listing.classificationProvenance === 'self_attested' ? ' — self-attested' : ''}
              </span>
            )}
            {listing.verificationStatus === 'verified' && (
              <span
                className="inline-flex items-center gap-1 bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wide text-emerald-700"
                title={DIRECTORY_VERIFIED_EXPLANATION}
              >
                <ShieldCheck size={13} /> Verified by WSF
              </span>
            )}
            {listing.categories?.map((c) => (
              <span key={c.id} className="border border-taupe-300 px-2.5 py-1.5 text-xs font-medium text-charcoal-600">{c.name}</span>
            ))}
          </div>
          {listing.verificationStatus === 'verified' && (
            <p className="mt-2 max-w-xl text-xs text-charcoal-600/70">{DIRECTORY_VERIFIED_EXPLANATION}</p>
          )}

          {listing.serviceSummary && <p className="mt-6 max-w-2xl text-lg text-charcoal-600">{listing.serviceSummary}</p>}
        </div>
      </div>

      <div className="container-editorial space-y-10 py-14">
        {listing.keyServices?.length > 0 && (
          <div>
            <p className="eyebrow mb-3">Key services</p>
            <div className="flex flex-wrap gap-2">
              {listing.keyServices.map((s) => (
                <span key={s} className="border border-taupe-200 bg-white px-3 py-1.5 text-sm text-charcoal-600">{s}</span>
              ))}
            </div>
          </div>
        )}

        {listing.serviceModes?.length > 0 && (
          <div>
            <p className="eyebrow mb-3">Service coverage</p>
            <p className="text-sm text-charcoal-600">{listing.serviceModes.map((m) => DIRECTORY_SERVICE_MODE_LABELS[m]).join(', ')}</p>
          </div>
        )}

        {(listing.publicContactEmail || listing.publicContactPhone) && (
          <div>
            <p className="eyebrow mb-3">Contact</p>
            <div className="space-y-1 text-sm text-charcoal-600">
              {listing.publicContactEmail && (
                <p><a href={`mailto:${listing.publicContactEmail}`} className="text-burgundy-600 hover:underline">{listing.publicContactEmail}</a></p>
              )}
              {listing.publicContactPhone && <p>{listing.publicContactPhone}</p>}
            </div>
          </div>
        )}

        {jobs.length > 0 && (
          <div>
            <p className="eyebrow mb-5">Open roles at {org.name}</p>
            <div className="grid grid-cols-1 gap-4">
              {jobs.map((j) => (
                <JobCard key={j.id} job={j} />
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-taupe-200 pt-8">
          <Link to={`/organizations/${org.slug}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-burgundy-600 hover:underline">
            View {org.name}'s full profile <ArrowUpRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  )
}
