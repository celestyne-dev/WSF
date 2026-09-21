import { Link } from 'react-router-dom'
import { MapPin, Clock } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { formatSalary, formatDeadline } from '../../utils/format'

export default function JobCard({ job }) {
  if (!job) return null
  return (
    <Link
      to={`/jobs/${job.slug}`}
      className="group flex items-start gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      <MediaImage
        media={job.logoMedia}
        variant="thumbnail"
        mediaPath={job.logo}
        alt={`${job.company} logo`}
        width={112}
        height={112}
        aspect={1}
        className="h-14 w-14 shrink-0 border border-taupe-100 object-cover"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">
            {job.title}
          </h3>
          {job.featured && (
            <span className="shrink-0 bg-burgundy-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">
              Featured
            </span>
          )}
        </div>
        <p className="mt-0.5 text-sm font-medium text-charcoal-600">{job.company}</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-charcoal-600">
          <span className="inline-flex items-center gap-1">
            <MapPin size={13} /> {job.location} &middot; {job.workMode}
          </span>
          <span>{job.employmentType}</span>
          <span>{formatSalary(job)}</span>
        </div>
        <div className="mt-2 inline-flex items-center gap-1 text-xs text-charcoal-600">
          <Clock size={13} /> {formatDeadline(job.deadline)}
        </div>
      </div>
    </Link>
  )
}
