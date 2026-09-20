import { useParams } from 'react-router-dom'
import { Calendar, MapPin, Clock, Ticket } from 'lucide-react'
import { getEventBySlug } from '../mock/events'
import { getPersonBySlug } from '../mock/people'
import { getOrganizationBySlug } from '../mock/organizations'
import { formatDate, formatCurrency } from '../utils/format'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import PersonCard from '../components/cards/PersonCard'
import NotFoundPage from './NotFoundPage'

export default function EventDetailPage() {
  const { slug } = useParams()
  const event = getEventBySlug(slug)
  if (!event) return <NotFoundPage />

  const speakers = (event.speakers || []).map((s) => getPersonBySlug(s)).filter(Boolean)
  const sponsors = (event.sponsors || []).map((s) => getOrganizationBySlug(s)).filter(Boolean)

  useSeo({
    title: `${event.title} | Women Shaping Futures Events`,
    description: event.description,
    canonical: `https://womenshapingfutures.org/events/${event.slug}`,
  })

  return (
    <div>
      <div className="relative">
        <MediaImage mediaPath={event.coverImage} alt={event.title} width={1920} height={720} aspect={2.6} tone="burgundy" priority className="h-64 w-full object-cover sm:h-96" />
        <div className="absolute inset-0 bg-gradient-to-t from-charcoal-800/80 to-transparent" />
        <div className="container-editorial absolute inset-x-0 bottom-0 pb-8 text-ivory">
          <Breadcrumb items={[{ label: 'Events', to: '/events' }, { label: event.title }]} />
          <p className="eyebrow mt-3 !text-blush-200">{event.type}</p>
          <h1 className="mt-1 font-serif text-3xl font-semibold sm:text-4xl">{event.title}</h1>
        </div>
      </div>

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          <p className="text-lg leading-relaxed text-charcoal-600">{event.description}</p>

          {event.agenda?.length > 0 && (
            <div className="mt-10">
              <h2 className="font-serif text-2xl font-semibold text-charcoal">Agenda</h2>
              <ul className="mt-4 divide-y divide-taupe-200">
                {event.agenda.map((item) => (
                  <li key={item.time} className="flex gap-6 py-3">
                    <span className="w-16 shrink-0 text-sm font-semibold text-burgundy-600">{item.time}</span>
                    <span className="text-base text-charcoal-600">{item.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {speakers.length > 0 && (
            <div className="mt-10">
              <h2 className="font-serif text-2xl font-semibold text-charcoal">Speakers</h2>
              <div className="mt-5 grid grid-cols-2 gap-6 sm:grid-cols-3">
                {speakers.map((p) => (
                  <PersonCard key={p.slug} person={p} />
                ))}
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <div className="border border-taupe-200 p-5">
            <ul className="space-y-4 text-sm text-charcoal-600">
              <li className="flex items-start gap-2">
                <Calendar size={16} className="mt-0.5 shrink-0" />
                {formatDate(event.date, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}, {event.startTime}–{event.endTime}
              </li>
              <li className="flex items-start gap-2">
                <MapPin size={16} className="mt-0.5 shrink-0" />
                {event.venue ? `${event.venue}, ${event.location}` : event.location}
              </li>
              <li className="flex items-start gap-2">
                <Clock size={16} className="mt-0.5 shrink-0" />
                {event.timezone.replace('_', ' ')}
              </li>
              <li className="flex items-start gap-2">
                <Ticket size={16} className="mt-0.5 shrink-0" />
                {formatCurrency(event.ticketPrice, event.currency)}
              </li>
            </ul>
            <a href={event.registrationUrl} className="btn-primary mt-5 flex w-full">
              {event.ticketPrice ? 'Get tickets' : 'Register free'}
            </a>
          </div>

          {sponsors.length > 0 && (
            <div>
              <p className="eyebrow mb-3">Sponsored by</p>
              <div className="flex flex-wrap gap-4">
                {sponsors.map((s) => (
                  <MediaImage key={s.slug} mediaPath={s.logo} alt={s.name} width={140} height={70} aspect={2} tone="taupe" className="h-9 w-auto" />
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
