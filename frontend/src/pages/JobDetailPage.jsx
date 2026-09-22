import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { MapPin, Briefcase, Clock, DollarSign, AlertCircle } from 'lucide-react'
import { fetchJobBySlug, fetchJobs } from '../api/jobs'
import { formatSalary, formatDate } from '../utils/format'
import { resolveImage } from '../utils/media'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import JobCard from '../components/cards/JobCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

const EMPLOYMENT_TYPE_SCHEMA = {
  'Full-time': 'FULL_TIME',
  'Part-time': 'PART_TIME',
  Contract: 'CONTRACTOR',
  Temporary: 'TEMPORARY',
  Internship: 'INTERN',
}

// Valid schema.org JobPosting structured data — built only from fields
// this job record actually carries. Nothing is fabricated to "complete"
// the schema.
function useJobStructuredData(job, canonicalUrl) {
  useEffect(() => {
    if (!job) return
    const data = {
      '@context': 'https://schema.org',
      '@type': 'JobPosting',
      title: job.title,
      description: job.shortDescription || job.title,
      datePosted: job.publishedDate || undefined,
      ...(job.deadline ? { validThrough: new Date(job.deadline).toISOString() } : {}),
      ...(job.employmentType && EMPLOYMENT_TYPE_SCHEMA[job.employmentType]
        ? { employmentType: EMPLOYMENT_TYPE_SCHEMA[job.employmentType] }
        : {}),
      hiringOrganization: {
        '@type': 'Organization',
        name: job.company,
        ...(job.logo ? { logo: resolveImage(job.logo, { width: 200, height: 200 }) } : {}),
      },
      ...(job.workMode === 'Remote'
        ? {
            jobLocationType: 'TELECOMMUTE',
            ...(job.remoteScope === 'worldwide'
              ? { applicantLocationRequirements: { '@type': 'Country', name: 'Anywhere' } }
              : {}),
            ...(job.remoteScope === 'country' && job.country
              ? { applicantLocationRequirements: { '@type': 'Country', name: job.country.name } }
              : {}),
            ...(job.remoteScope === 'region' && job.remoteRegion
              ? { applicantLocationRequirements: { '@type': 'Place', name: job.remoteRegion } }
              : {}),
          }
        : job.location || job.country
          ? {
              jobLocation: {
                '@type': 'Place',
                address: {
                  '@type': 'PostalAddress',
                  ...(job.location ? { addressLocality: job.location } : {}),
                  ...(job.country ? { addressCountry: job.country.code } : {}),
                },
              },
            }
          : {}),
      ...(job.salaryMin && job.currency
        ? {
            baseSalary: {
              '@type': 'MonetaryAmount',
              currency: job.currency,
              value: {
                '@type': 'QuantitativeValue',
                ...(job.salaryMin ? { minValue: job.salaryMin } : {}),
                ...(job.salaryMax ? { maxValue: job.salaryMax } : {}),
                unitText: (job.salaryPeriod || 'year').toUpperCase().slice(0, 4),
              },
            },
          }
        : {}),
    }
    let el = document.head.querySelector('script[data-job-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-job-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [job, canonicalUrl])
}

export default function JobDetailPage() {
  const { slug } = useParams()
  const [job, setJob] = useState(undefined)
  const [moreJobs, setMoreJobs] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setJob(undefined)
    setMoreJobs([])
    setError(null)

    fetchJobBySlug(slug)
      .then((data) => {
        if (!active) return
        setJob(data)
        if (!data) return
        fetchJobs({ industry: data.industry, pageSize: 4 })
          .then((res) => active && setMoreJobs(res.items.filter((j) => j.slug !== slug).slice(0, 3)))
          .catch(() => {})
      })
      .catch(() => active && setError('Something went wrong loading this job. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = `https://womenshapingfutures.org/jobs/${slug}`

  useSeo(
    job
      ? {
          title: job.seo?.title || `${job.title} at ${job.company} | Women Shaping Futures Jobs`,
          description: job.seo?.description || job.shortDescription,
          canonical: job.seo?.canonical || canonicalUrl,
          image: job.logo ? resolveImage(job.logo, { width: 1200, height: 630 }) : undefined,
          robots: job.seo?.robots,
        }
      : {},
  )

  useJobStructuredData(job, canonicalUrl)

  function handleApplyClick() {
    trackEvent('job_apply_click', { jobSlug: job.slug, company: job.company })
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this job" description={error} /></div>
  if (job === undefined) return <PageLoader />
  if (job === null) return <NotFoundPage />

  const remoteLabel =
    job.workMode === 'Remote'
      ? job.remoteScope === 'worldwide'
        ? 'Remote — worldwide'
        : job.remoteScope === 'region' && job.remoteRegion
          ? `Remote — ${job.remoteRegion}`
          : job.remoteScope === 'country' && job.country
            ? `Remote — ${job.country.name}`
            : 'Remote'
      : job.workMode

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Jobs', to: '/jobs' }, { label: job.title }]} />

          {job.sponsored && (
            <div className="mt-4 inline-flex items-center gap-2 border border-dashed border-taupe-300 bg-blush-50 px-4 py-2 text-xs text-charcoal-600">
              <span className="font-semibold uppercase tracking-wide text-burgundy-600">Sponsored</span>
              <span>This listing is a paid placement from {job.company}.</span>
            </div>
          )}

          {job.isClosed && (
            <div className="mt-4 flex items-center gap-2 border border-taupe-300 bg-taupe-100 px-4 py-3 text-sm text-charcoal-600">
              <AlertCircle size={16} className="shrink-0" />
              <span className="font-semibold">Applications closed</span> — this role is no longer accepting applications.
            </div>
          )}

          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            <MediaImage media={job.logoMedia} variant="thumbnail" mediaPath={job.logo} alt={`${job.company} logo`} width={160} height={160} aspect={1} className="h-20 w-20 border border-taupe-200 object-contain p-2" />
            <div>
              <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{job.title}</h1>
              {job.companySlug ? (
                <Link to={`/organizations/${job.companySlug}`} className="mt-1 inline-block text-lg font-medium text-charcoal-600 hover:text-burgundy-600">
                  {job.company}
                </Link>
              ) : (
                <p className="mt-1 text-lg font-medium text-charcoal-600">{job.company}</p>
              )}
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-charcoal-600">
            {(job.location || job.workMode) && (
              <span className="inline-flex items-center gap-1.5">
                <MapPin size={15} /> {[job.location, remoteLabel].filter(Boolean).join(' · ')}
              </span>
            )}
            {(job.employmentType || job.careerLevel) && (
              <span className="inline-flex items-center gap-1.5">
                <Briefcase size={15} /> {[job.employmentType, job.careerLevel].filter(Boolean).join(' · ')}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <DollarSign size={15} /> {formatSalary(job)}
            </span>
            {job.deadline && (
              <span className="inline-flex items-center gap-1.5">
                <Clock size={15} /> Apply by {formatDate(job.deadline)}
              </span>
            )}
          </div>
          {job.isClosed ? (
            <button type="button" disabled className="btn-secondary mt-6 inline-flex cursor-not-allowed opacity-60">
              Applications closed
            </button>
          ) : job.applicationUrl ? (
            <a href={job.applicationUrl} target="_blank" rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-6 inline-flex">
              Apply for this role
            </a>
          ) : null}
        </div>
      </div>

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          {job.shortDescription && <p className="text-lg leading-relaxed text-charcoal-600">{job.shortDescription}</p>}

          <ArticleContent blocks={job.description} />

          {(job.applicationInstructions || job.applicationUrl) && !job.isClosed && (
            <div className="mt-8 border border-taupe-200 bg-cream p-5">
              <p className="text-sm font-semibold text-charcoal">How to apply</p>
              {job.applicationInstructions && <p className="mt-1 text-sm text-charcoal-600">{job.applicationInstructions}</p>}
              {job.applicationUrl && (
                <a href={job.applicationUrl} target="_blank" rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-4 inline-flex">
                  Apply now
                </a>
              )}
            </div>
          )}
        </div>

        {job.companySlug && (
          <aside>
            <div className="border border-taupe-200 p-5">
              <p className="eyebrow mb-3">About {job.company}</p>
              <Link to={`/organizations/${job.companySlug}`} className="font-serif text-lg font-semibold text-charcoal hover:text-burgundy-600">
                View company profile &rarr;
              </Link>
            </div>
          </aside>
        )}
      </div>

      {moreJobs.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">More {job.industry} roles</p>
          <div className="grid grid-cols-1 gap-4">
            {moreJobs.map((j) => (
              <JobCard key={j.id} job={j} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
