import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Globe } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { fetchOrganizationBySlug } from '../api/taxonomies'
import { fetchJobs } from '../api/jobs'
import { fetchOpportunities } from '../api/opportunities'
import { fetchPeople } from '../api/people'
import { fetchArticles } from '../api/articles'
import { resolveImage } from '../utils/media'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import JobCard from '../components/cards/JobCard'
import OpportunityCard from '../components/cards/OpportunityCard'
import PersonCard from '../components/cards/PersonCard'
import ArticleCard from '../components/cards/ArticleCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

const TYPE_LABELS = {
  company: 'Company',
  nonprofit: 'Nonprofit',
  foundation: 'Foundation',
  government: 'Government organization',
  educational_institution: 'Educational institution',
  media_organization: 'Media organization',
  professional_association: 'Professional association',
  social_enterprise: 'Social enterprise',
  community_organization: 'Community organization',
  other: 'Other',
}

// Minimal schema.org Organization structured data — built only from
// fields the profile actually carries, never inferring business facts.
function useOrgStructuredData(org, canonicalUrl) {
  useEffect(() => {
    if (!org) return
    const data = {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: org.name,
      url: canonicalUrl,
      ...(org.website ? { sameAs: [org.website] } : {}),
      ...(org.logo ? { logo: resolveImage(org.logo, { width: 400, height: 400 }) } : {}),
      ...(org.foundedYear ? { foundingDate: String(org.foundedYear) } : {}),
    }
    let el = document.head.querySelector('script[data-org-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-org-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [org, canonicalUrl])
}

export default function OrganizationDetailPage() {
  const { slug } = useParams()
  const [org, setOrg] = useState(undefined)
  const [orgJobs, setOrgJobs] = useState([])
  const [orgOpportunities, setOrgOpportunities] = useState([])
  const [orgPeople, setOrgPeople] = useState([])
  const [orgArticles, setOrgArticles] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setOrg(undefined)
    setOrgJobs([])
    setOrgOpportunities([])
    setOrgPeople([])
    setOrgArticles([])
    setError(null)

    fetchOrganizationBySlug(slug)
      .then((data) => {
        if (!active) return
        setOrg(data)
        if (!data) return

        fetchJobs({ organization: slug, pageSize: 20 })
          .then((res) => active && setOrgJobs(res.items))
          .catch(() => {})
        fetchOpportunities({ organization: slug, pageSize: 20 })
          .then((res) => active && setOrgOpportunities(res.items))
          .catch(() => {})
        fetchPeople({ organization: slug, pageSize: 20 })
          .then((res) => active && setOrgPeople(res.items))
          .catch(() => {})
        fetchArticles({ organization: slug, pageSize: 6 })
          .then((res) => active && setOrgArticles(res.items))
          .catch(() => {})
      })
      .catch(() => active && setError('Something went wrong loading this organization. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = `https://womenshapingfutures.org/organizations/${slug}`

  useSeo(
    org
      ? {
          title: org.seo?.title || `${org.name} | Women Shaping Futures`,
          description: org.seo?.description || org.shortDescription,
          canonical: org.seo?.canonical || canonicalUrl,
          image: org.logo ? resolveImage(org.logo, { width: 1200, height: 630 }) : undefined,
          robots: org.seo?.robots,
        }
      : {},
  )

  useOrgStructuredData(org, canonicalUrl)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this organization" description={error} /></div>
  if (org === undefined) return <PageLoader />
  if (org === null) return <NotFoundPage />

  const metaLine = [TYPE_LABELS[org.type], org.industry, org.location || org.country?.name].filter(Boolean).join(' · ')

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Organizations', to: '/organizations' }, { label: org.name }]} />
          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            {org.logo ? (
              <div className="flex h-24 w-24 shrink-0 items-center justify-center border border-taupe-200 bg-white p-3">
                <MediaImage media={org.logoMedia} variant="thumbnail" mediaPath={org.logo} alt={`${org.name} logo`} width={200} height={200} aspect={1} className="h-full w-full object-contain" />
              </div>
            ) : null}
            <div>
              <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{org.name}</h1>
              {metaLine && <p className="mt-1 text-base text-charcoal-600">{metaLine}</p>}
              {org.foundedYear && <p className="mt-1 text-sm text-charcoal-600">Founded {org.foundedYear}</p>}
              {(org.website || org.social?.linkedin || org.social?.twitter || org.social?.instagram) && (
                <div className="mt-3 flex gap-4">
                  {org.website && (
                    <a href={org.website} target="_blank" rel="noreferrer" aria-label="Website" className="text-charcoal-600 hover:text-burgundy-600">
                      <Globe size={17} />
                    </a>
                  )}
                  {org.social?.linkedin && (
                    <a href={`https://linkedin.com/company/${org.social.linkedin}`} target="_blank" rel="noreferrer" aria-label="LinkedIn" className="text-charcoal-600 hover:text-burgundy-600">
                      <SocialIcon name="linkedin" size={17} />
                    </a>
                  )}
                  {org.social?.twitter && (
                    <a href={`https://twitter.com/${org.social.twitter}`} target="_blank" rel="noreferrer" aria-label="Twitter" className="text-charcoal-600 hover:text-burgundy-600">
                      <SocialIcon name="twitter" size={17} />
                    </a>
                  )}
                  {org.social?.instagram && (
                    <a href={`https://instagram.com/${org.social.instagram}`} target="_blank" rel="noreferrer" aria-label="Instagram" className="text-charcoal-600 hover:text-burgundy-600">
                      <SocialIcon name="instagram" size={17} />
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>

          {org.shortDescription && <p className="mt-6 max-w-2xl text-lg text-charcoal-600">{org.shortDescription}</p>}
          {org.description?.length > 0 && (
            <div className="mt-4 max-w-2xl">
              <ArticleContent blocks={org.description} />
            </div>
          )}
        </div>
      </div>

      <div className="container-editorial space-y-14 py-14">
        {orgPeople.length > 0 && (
          <div>
            <p className="eyebrow mb-5">People at {org.name}</p>
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
              {orgPeople.map((p) => (
                <PersonCard key={p.slug} person={p} />
              ))}
            </div>
          </div>
        )}
        {orgJobs.length > 0 && (
          <div>
            <p className="eyebrow mb-5">Open roles</p>
            <div className="grid grid-cols-1 gap-4">
              {orgJobs.map((j) => (
                <JobCard key={j.id} job={j} />
              ))}
            </div>
          </div>
        )}
        {orgOpportunities.length > 0 && (
          <div>
            <p className="eyebrow mb-5">Opportunities</p>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
              {orgOpportunities.map((o) => (
                <OpportunityCard key={o.id} opportunity={o} />
              ))}
            </div>
          </div>
        )}
        {orgArticles.length > 0 && (
          <div>
            <p className="eyebrow mb-5">Stories featuring {org.name}</p>
            <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-3">
              {orgArticles.map((a) => (
                <ArticleCard key={a.id} article={a} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
