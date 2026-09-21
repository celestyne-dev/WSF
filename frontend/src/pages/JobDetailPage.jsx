import { useParams, Link } from 'react-router-dom'
import { MapPin, Briefcase, Clock, DollarSign } from 'lucide-react'
import { getJobBySlug } from '../mock/jobs'
import { jobs } from '../mock/jobs'
import { formatSalary, formatDate } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import JobCard from '../components/cards/JobCard'
import NotFoundPage from './NotFoundPage'

export default function JobDetailPage() {
  const { slug } = useParams()
  const job = getJobBySlug(slug)
  if (!job) return <NotFoundPage />

  const moreJobs = jobs.filter((j) => j.slug !== slug && j.industry === job.industry).slice(0, 3)

  useSeo({
    title: `${job.title} at ${job.company} | Women Shaping Futures Jobs`,
    description: job.description,
    canonical: `https://womenshapingfutures.org/jobs/${job.slug}`,
  })

  function handleApplyClick() {
    trackEvent('job_apply_click', { jobSlug: job.slug, company: job.company })
  }

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Jobs', to: '/jobs' }, { label: job.title }]} />
          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            <MediaImage mediaPath={job.logo} alt={`${job.company} logo`} width={160} height={160} aspect={1} className="h-20 w-20 border border-taupe-200 object-cover" />
            <div>
              <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{job.title}</h1>
              <p className="mt-1 text-lg font-medium text-charcoal-600">{job.company}</p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-charcoal-600">
            <span className="inline-flex items-center gap-1.5">
              <MapPin size={15} /> {job.location} &middot; {job.workMode}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Briefcase size={15} /> {job.employmentType} &middot; {job.careerLevel}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <DollarSign size={15} /> {formatSalary(job)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Clock size={15} /> Apply by {formatDate(job.deadline)}
            </span>
          </div>
          <a href={job.applicationUrl} target="_blank" rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-6 inline-flex">
            Apply for this role
          </a>
        </div>
      </div>

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          <p className="text-lg leading-relaxed text-charcoal-600">{job.description}</p>

          <h2 className="mt-8 font-serif text-xl font-semibold text-charcoal">Responsibilities</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-base text-charcoal-600">
            {job.responsibilities.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>

          <h2 className="mt-8 font-serif text-xl font-semibold text-charcoal">Requirements</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-base text-charcoal-600">
            {job.requirements.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>

          <h2 className="mt-8 font-serif text-xl font-semibold text-charcoal">Benefits</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-base text-charcoal-600">
            {job.benefits.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>

          <div className="mt-8 border border-taupe-200 bg-cream p-5">
            <p className="text-sm font-semibold text-charcoal">How to apply</p>
            <p className="mt-1 text-sm text-charcoal-600">{job.applicationInstructions}</p>
            <a href={job.applicationUrl} target="_blank" rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-4 inline-flex">
              Apply now
            </a>
          </div>
        </div>

        <aside>
          <div className="border border-taupe-200 p-5">
            <p className="eyebrow mb-3">About {job.company}</p>
            <Link to={`/organizations/${job.companySlug}`} className="font-serif text-lg font-semibold text-charcoal hover:text-burgundy-600">
              View company profile &rarr;
            </Link>
          </div>
        </aside>
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
