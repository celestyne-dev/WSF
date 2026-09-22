import { Link } from 'react-router-dom'
import { MapPin, Clock } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { formatSalary, formatDeadline } from '../../utils/format'

export default function JobCard({ job }) {
  if (!job) return null
  const locationLine = job.workMode === 'Remote' ? [job.location, 'Remote'].filter(Boolean).join(' · ') : [job.location, job.workMode].filter(Boolean).join(' · ')
  return (
    <Link
      to={`/jobs/${job.slug}`}
      className="group flex items-start gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      {job.logo ? (
        <div className="flex h-14 w-14 shrink-0 items-center justify-center border border-taupe-100 bg-white p-1.5">
          <MediaImage
            media={job.logoMedia}
            variant="thumbnail"
            mediaPath={job.logo}
            alt={`${job.company} logo`}
            width={112}
            height={112}
            aspect={1}
            className="h-full w-full object-contain"
          />
        </div>
      ) : (
        <div className="flex h-14 w-14 shrink-0 items-center justify-center border border-taupe-100 bg-taupe-100 font-serif text-base font-semibold text-charcoal-600">
          {job.company?.[0]}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">
            {job.title}
          </h3>
          <div className="flex shrink-0 gap-1.5">
            {job.featured && (
              <span className="bg-burgundy-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">
                Featured
              </span>
            )}
            {job.sponsored && (
              <span className="bg-taupe-200 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">
                Sponsored
              </span>
            )}
          </div>
        </div>
        <p className="mt-0.5 text-sm font-medium text-charcoal-600">{job.company}</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-charcoal-600">
          {locationLine && (
            <span className="inline-flex items-center gap-1">
              <MapPin size={13} /> {locationLine}
            </span>
          )}
          {job.employmentType && <span>{job.employmentType}</span>}
          <span>{formatSalary(job)}</span>
        </div>
        {job.isClosed ? (
          <div className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-charcoal-600/70">Applications closed</div>
        ) : (
          job.deadline && (
            <div className="mt-2 inline-flex items-center gap-1 text-xs text-charcoal-600">
              <Clock size={13} /> {formatDeadline(job.deadline)}
            </div>
          )
        )}
      </div>
    </Link>
  )
}
