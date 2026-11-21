import { Link } from 'react-router-dom'
import { MapPin, Clock } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { resolveAltText } from '../../utils/media'
import { formatSalary } from '../../utils/format'
import { closingLabel, isClosingSoon, postedLabel } from '../../utils/listingDates'

// Hierarchy: role, employer, location · work mode, employment type · level,
// salary (only when public), then posted / closing dates. "Closing soon" is
// a text label, never colour alone.
export default function JobCard({ job }) {
  if (!job) return null
  const locationLine = [job.location, job.workMode].filter(Boolean).join(' · ')
  const typeLine = [job.employmentType, job.careerLevel].filter(Boolean).join(' · ')
  const salary = job.salaryVisible === false ? null : (job.salaryMin || job.salaryMax ? formatSalary(job) : null)
  const soon = isClosingSoon(job.closing)
  return (
    <Link
      to={`/jobs/${job.slug}`}
      className="group flex overflow-hidden rounded-card items-start gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40"
    >
      {job.logo ? (
        <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-control border border-taupe-100 bg-white p-1.5">
          <MediaImage
            media={job.logoMedia}
            variant="thumbnail"
            mediaPath={job.logo}
            alt={resolveAltText(job.logoMedia, `${job.company} logo`)}
            width={112}
            height={112}
            aspect={1}
            sizes="56px"
            className="h-full w-full object-contain"
          />
        </div>
      ) : (
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-control border border-taupe-100 bg-taupe-100 font-serif text-base font-semibold text-charcoal-600">
          {job.company?.[0]}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
            {job.title}
          </h3>
          <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
            {job.accessType === 'circle_only' && (
              <span className="bg-plum-600/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-plum-700">WSF Circle</span>
            )}
            {job.featured && (
              <span className="bg-burgundy-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</span>
            )}
            {job.sponsored && (
              <span className="bg-taupe-200 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">Sponsored</span>
            )}
          </div>
        </div>
        <p className="mt-0.5 text-sm font-medium text-charcoal-600">{job.company}</p>
        {locationLine && (
          <p className="mt-2 inline-flex items-center gap-1 text-xs text-charcoal-600">
            <MapPin size={13} aria-hidden="true" /> {locationLine}
          </p>
        )}
        {typeLine && <p className="mt-1 text-xs text-charcoal-600">{typeLine}</p>}
        {salary && <p className="mt-1 text-xs font-semibold text-charcoal">{salary}</p>}
        <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-charcoal-600">
          {job.publishedDate && <span>{postedLabel(job.publishedDate)}</span>}
          {job.isClosed ? (
            <span className="font-semibold text-charcoal-600">Applications closed</span>
          ) : (
            job.closing && (
              <span className={`inline-flex items-center gap-1 ${soon ? 'font-semibold text-burgundy-700' : ''}`}>
                <Clock size={12} aria-hidden="true" /> {closingLabel(job.closing)}
              </span>
            )
          )}
          {soon && !job.isClosed && (
            <span className="rounded-control bg-burgundy-500/10 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-burgundy-700">
              Closing soon
            </span>
          )}
        </div>
      </div>
    </Link>
  )
}
