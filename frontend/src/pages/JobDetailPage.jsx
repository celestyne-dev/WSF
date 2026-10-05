import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { MapPin, Briefcase, Clock, DollarSign, AlertCircle, Calendar, Building2 } from 'lucide-react'
import { fetchJobBySlug, fetchJobs, accessJob } from '../api/jobs'
import { fetchOrganizationBySlug } from '../api/taxonomies'
import { fetchArticles } from '../api/articles'
import { formatSalary, formatDate } from '../utils/format'
import { resolveImage } from '../utils/media'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ShareBar from '../components/ui/ShareBar'
import SaveButton from '../components/account/SaveButton'
import NewsletterForm from '../components/ui/NewsletterForm'
import ArticleContent from '../components/article/ArticleContent'
import ArticleCard from '../components/cards/ArticleCard'
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
                  ...(job.city ? { addressLocality: job.city } : job.location ? { addressLocality: job.location } : {}),
                  ...(job.country ? { addressCountry: job.country.code } : {}),
                },
              },
            }
          : {}),
      ...(job.salaryMin && job.currency && job.salaryVisible
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

// The one place a circle_only Job's gated application channel is
// requested and opened — public jobs never call this (their
// applicationUrl/applicationEmail already arrive on the detail response
// itself). Backend remains authoritative either way: job.viewerCanAccess
// is a UI guidance hint, not POST /access's own check. `circleAccess`
// (the just-granted {applicationUrl, applicationEmail,
// applicationInstructions}) is plain component state — never persisted
// to Redux/localStorage/sessionStorage, and cleared on any failure
// (URL+email+instructions together, as one unit) so a stale channel can
// never linger in the UI.
function CircleApplyCta({ job, accessToken, pending, circleAccess, onApply, onSignIn }) {
  if (!accessToken) {
    return (
      <div className="mt-6 border border-taupe-200 bg-cream p-4">
        <p className="text-sm font-semibold text-charcoal">WSF Circle role</p>
        <button type="button" onClick={onSignIn} className="btn-primary mt-3 inline-flex">
          Sign in to access application
        </button>
      </div>
    )
  }
  if (!job.viewerCanAccess && !circleAccess) {
    return (
      <div className="mt-6 border border-taupe-200 bg-cream p-4">
        <p className="text-sm font-semibold text-charcoal">Included with WSF Circle</p>
        <Link to="/circle" className="btn-primary mt-3 inline-flex">
          Explore WSF Circle
        </Link>
      </div>
    )
  }
  return (
    <button type="button" onClick={onApply} disabled={pending} className="btn-primary mt-6 inline-flex disabled:opacity-60">
      {pending ? 'Preparing…' : 'Apply now'}
    </button>
  )
}

export default function JobDetailPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [job, setJob] = useState(undefined)
  const [company, setCompany] = useState(null)
  const [moreJobs, setMoreJobs] = useState([])
  const [relatedArticles, setRelatedArticles] = useState([])
  const [error, setError] = useState(null)
  const [applying, setApplying] = useState(false)
  const [circleAccess, setCircleAccess] = useState(null)

  useEffect(() => {
    let active = true
    setJob(undefined)
    setCompany(null)
    setMoreJobs([])
    setRelatedArticles([])
    setError(null)
    setCircleAccess(null)

    fetchJobBySlug(slug)
      .then((data) => {
        if (!active) return
        setJob(data)
        if (!data) return
        fetchJobs({ industry: data.industry, pageSize: 4 })
          .then((res) => active && setMoreJobs(res.items.filter((j) => j.slug !== slug).slice(0, 3)))
          .catch(() => {})
        if (data.companySlug) {
          fetchOrganizationBySlug(data.companySlug)
            .then((org) => active && setCompany(org))
            .catch(() => {})
        }
        // "Opportunities" is WSF's editorial topic covering jobs,
        // scholarships, fellowships, and grants — a genuine, non-fabricated
        // relation to show alongside a job listing, rather than guessing
        // at an industry-specific topic match that doesn't exist.
        fetchArticles({ topic: 'opportunities', pageSize: 2 })
          .then((res) => active && setRelatedArticles(res.items))
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
          // Expired/closed listings stay reachable for record but
          // shouldn't rank — thin, stale content search engines shouldn't
          // index, unless an editor explicitly overrides it.
          robots: job.seo?.robots || (job.isClosed ? 'noindex, follow' : undefined),
        }
      : {},
  )

  useJobStructuredData(job, canonicalUrl)

  function handleApplyClick() {
    trackEvent('job_apply_click', { jobSlug: job.slug, company: job.company })
  }

  async function handleCircleApply() {
    trackEvent('job_apply_click', { jobSlug: job.slug, company: job.company })
    setApplying(true)
    try {
      const result = await accessJob(job.slug)
      setCircleAccess(result)
      const href = result.applicationUrl || (result.applicationEmail ? `mailto:${result.applicationEmail}` : null)
      if (href) window.open(href, result.applicationUrl ? '_blank' : undefined, 'noopener,noreferrer')
    } catch (err) {
      setCircleAccess(null)
      const code = err?.response?.data?.error?.code
      if (code === 'circle_required') {
        toast.error('WSF Circle access required.')
      } else {
        toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
      }
    } finally {
      setApplying(false)
    }
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

  const applyHref = job.applicationUrl || (job.applicationEmail ? `mailto:${job.applicationEmail}` : null)
  const applyLabel = job.applicationUrl ? 'Apply for this role' : 'Email your application'

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

          {job.accessType === 'circle_only' && (
            <div className="mt-4 inline-flex items-center gap-2 bg-plum-500/90 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-ivory">
              WSF Circle
            </div>
          )}

          {job.isClosed && (
            <div className="mt-4 flex items-center gap-2 border border-taupe-300 bg-taupe-100 px-4 py-3 text-sm text-charcoal-600">
              <AlertCircle size={16} className="shrink-0" />
              <span className="font-semibold">Applications closed</span> — this role is no longer accepting applications.
            </div>
          )}

          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
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
            <SaveButton contentType="job" contentId={job.id} />
          </div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-charcoal-600">
            {(job.location || job.city || job.workMode) && (
              <span className="inline-flex items-center gap-1.5">
                <MapPin size={15} /> {[job.location || job.city, remoteLabel].filter(Boolean).join(' · ')}
              </span>
            )}
            {(job.employmentType || job.careerLevel) && (
              <span className="inline-flex items-center gap-1.5">
                <Briefcase size={15} /> {[job.employmentType, job.careerLevel].filter(Boolean).join(' · ')}
              </span>
            )}
            {job.industry && (
              <span className="inline-flex items-center gap-1.5">
                <Building2 size={15} /> {job.industry}
              </span>
            )}
            {job.salaryVisible !== false && (
              <span className="inline-flex items-center gap-1.5">
                <DollarSign size={15} /> {formatSalary(job)}
              </span>
            )}
            {job.publishedDate && (
              <span className="inline-flex items-center gap-1.5">
                <Calendar size={15} /> Posted {formatDate(job.publishedDate)}
              </span>
            )}
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
          ) : job.accessType === 'circle_only' ? (
            <CircleApplyCta
              job={job}
              accessToken={accessToken}
              pending={applying}
              circleAccess={circleAccess}
              onApply={handleCircleApply}
              onSignIn={() => navigate('/login')}
            />
          ) : applyHref ? (
            <a href={applyHref} target={job.applicationUrl ? '_blank' : undefined} rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-6 inline-flex">
              {applyLabel}
            </a>
          ) : null}
        </div>
      </div>

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          {job.shortDescription && <p className="text-lg leading-relaxed text-charcoal-600">{job.shortDescription}</p>}

          <ArticleContent blocks={job.description} />

          {job.responsibilities?.length > 0 && (
            <div className="mt-8">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Responsibilities</h2>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-base text-charcoal-600">
                {job.responsibilities.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {job.requirements?.length > 0 && (
            <div className="mt-8">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Requirements</h2>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-base text-charcoal-600">
                {job.requirements.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {job.qualifications?.length > 0 && (
            <div className="mt-8">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Qualifications</h2>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-base text-charcoal-600">
                {job.qualifications.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {job.skills?.length > 0 && (
            <div className="mt-8">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Skills</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {job.skills.map((skill, i) => (
                  <span key={i} className="bg-taupe-100 px-3 py-1 text-sm text-charcoal-600">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {job.benefits?.length > 0 && (
            <div className="mt-8">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Benefits</h2>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-base text-charcoal-600">
                {job.benefits.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {job.accessType === 'circle_only'
            ? circleAccess &&
              !job.isClosed && (
                <div className="mt-8 border border-taupe-200 bg-cream p-5">
                  <p className="text-sm font-semibold text-charcoal">How to apply</p>
                  {circleAccess.applicationInstructions && (
                    <p className="mt-1 text-sm text-charcoal-600">{circleAccess.applicationInstructions}</p>
                  )}
                  {(circleAccess.applicationUrl || circleAccess.applicationEmail) && (
                    <a
                      href={circleAccess.applicationUrl || `mailto:${circleAccess.applicationEmail}`}
                      target={circleAccess.applicationUrl ? '_blank' : undefined}
                      rel="noreferrer"
                      className="btn-primary mt-4 inline-flex"
                    >
                      {circleAccess.applicationUrl ? 'Apply now' : 'Email your application'}
                    </a>
                  )}
                </div>
              )
            : (job.applicationInstructions || applyHref) &&
              !job.isClosed && (
                <div className="mt-8 border border-taupe-200 bg-cream p-5">
                  <p className="text-sm font-semibold text-charcoal">How to apply</p>
                  {job.applicationInstructions && <p className="mt-1 text-sm text-charcoal-600">{job.applicationInstructions}</p>}
                  {applyHref && (
                    <a href={applyHref} target={job.applicationUrl ? '_blank' : undefined} rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-4 inline-flex">
                      {applyLabel}
                    </a>
                  )}
                </div>
              )}

          <div className="mt-10 border-t border-taupe-200 pt-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Share this role</p>
            <ShareBar title={job.title} url={canonicalUrl} trackEventName="job_share_click" trackPayload={{ jobSlug: job.slug }} />
          </div>
        </div>

        {(company || job.companySlug) && (
          <aside>
            <div className="border border-taupe-200 p-5">
              <p className="eyebrow mb-3">About {job.company}</p>
              {company?.logo && (
                <MediaImage media={company.logoMedia} variant="thumbnail" mediaPath={company.logo} alt={job.company} width={120} height={120} aspect={1} className="mb-3 h-14 w-14 object-contain" />
              )}
              {company?.shortDescription && <p className="mb-3 text-sm text-charcoal-600">{company.shortDescription}</p>}
              <Link to={`/organizations/${job.companySlug}`} className="font-serif text-base font-semibold text-charcoal hover:text-burgundy-600">
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

      {relatedArticles.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">Related reading</p>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            {relatedArticles.map((article) => (
              <ArticleCard key={article.slug} article={article} />
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-taupe-200 bg-charcoal-800 py-14 text-ivory">
        <div className="container-editorial flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-serif text-2xl font-semibold">Never miss a role like this</h2>
            <p className="mt-1 text-sm text-ivory/70">Curated jobs and opportunities for women, delivered every Thursday.</p>
          </div>
          <NewsletterForm variant="dark" source="job_detail" />
        </div>
      </div>
    </div>
  )
}
