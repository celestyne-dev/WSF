import { Link } from 'react-router-dom'
import { MapPin } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { formatDate } from '../../utils/format'

export default function EventCard({ event }) {
  if (!event) return null
  const date = new Date(event.date)
  return (
    <Link to={`/events/${event.slug}`} className="group flex gap-4 border border-taupe-200 bg-white p-4 transition-colors hover:border-burgundy-500/40">
      <div className="flex w-16 shrink-0 flex-col items-center justify-center bg-plum-600 py-2 text-ivory">
        <span className="text-xs font-semibold uppercase tracking-wide">{date.toLocaleDateString('en-US', { month: 'short' })}</span>
        <span className="font-serif text-2xl font-semibold">{date.getDate()}</span>
      </div>
      <div className="min-w-0 flex-1">
        <span className="eyebrow">{event.type}</span>
        <h3 className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {event.title}
        </h3>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-charcoal-600">
          <span className="inline-flex items-center gap-1">
            <MapPin size={13} /> {event.location}
          </span>
          <span>{formatDate(event.date, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}</span>
        </div>
      </div>
      {event.coverImage && (
        <MediaImage
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
