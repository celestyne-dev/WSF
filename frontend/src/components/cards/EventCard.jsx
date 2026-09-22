import { Link } from 'react-router-dom'
import { MapPin, Globe2 } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { formatDate, formatCurrency } from '../../utils/format'

export default function EventCard({ event }) {
  if (!event) return null
  const date = new Date(event.date)
  const locationLine = event.format === 'virtual' ? 'Online' : [event.location, event.format === 'hybrid' ? 'Hybrid' : null].filter(Boolean).join(' · ')

  return (
    <Link to={`/events/${event.slug}`} className="group flex gap-4 border border-taupe-200 bg-white p-4 transition-colors hover:border-burgundy-500/40">
      <div className="flex w-16 shrink-0 flex-col items-center justify-center bg-plum-600 py-2 text-ivory">
        <span className="text-xs font-semibold uppercase tracking-wide">{date.toLocaleDateString('en-US', { month: 'short' })}</span>
        <span className="font-serif text-2xl font-semibold">{date.getDate()}</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <span className="eyebrow">{event.type}</span>
          <div className="flex shrink-0 gap-1.5">
            {event.featured && (
              <span className="bg-burgundy-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</span>
            )}
            {event.sponsored && (
              <span className="bg-taupe-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-charcoal-600">Sponsored</span>
            )}
          </div>
        </div>
        <h3 className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {event.title}
        </h3>
        {event.organizer && <p className="mt-0.5 text-sm font-medium text-charcoal-600">{event.organizer}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-charcoal-600">
          {locationLine && (
            <span className="inline-flex items-center gap-1">
              {event.format === 'virtual' ? <Globe2 size={13} /> : <MapPin size={13} />} {locationLine}
            </span>
          )}
          <span>
            {formatDate(event.date, { weekday: 'short', month: 'short', day: 'numeric' })}
            {event.startTime ? `, ${event.startTime}` : ''}
            {event.timezone ? ` ${event.timezone.split('/').pop().replace('_', ' ')}` : ''}
          </span>
        </div>
        <div className="mt-2 flex items-center gap-3 text-xs">
          {event.isCancelled ? (
            <span className="font-semibold text-rose-600">Event cancelled</span>
          ) : event.soldOut ? (
            <span className="font-semibold text-charcoal-600/70">Sold out</span>
          ) : (
            <span className="font-semibold text-burgundy-600">{formatCurrency(event.ticketPrice, event.currency)}</span>
          )}
        </div>
      </div>
      {event.coverImage && (
        <MediaImage
          media={event.coverMedia}
          variant="thumbnail"
          mediaPath={event.coverImage}
          alt={event.title}
          width={200}
          height={200}
          aspect={1}
          className="hidden h-20 w-20 shrink-0 object-cover sm:block"
        />
      )}
    </Link>
  )
}
