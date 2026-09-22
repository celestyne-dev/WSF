import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Calendar, MapPin, Clock, Ticket, Globe2, AlertCircle } from 'lucide-react'
import { fetchEventBySlug } from '../api/events'
import { fetchPersonBySlug } from '../api/people'
import { fetchOrganizationBySlug } from '../api/taxonomies'
import { formatDate, formatCurrency } from '../utils/format'
import { resolveImage } from '../utils/media'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import PersonCard from '../components/cards/PersonCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

const ATTENDANCE_MODE = {
  'in-person': 'https://schema.org/OfflineEventAttendanceMode',
  virtual: 'https://schema.org/OnlineEventAttendanceMode',
  hybrid: 'https://schema.org/MixedEventAttendanceMode',
}

// Valid schema.org Event structured data — built only from fields this
// event record actually carries. Nothing is fabricated to "complete" the
// schema; the private virtual join link is never included here even when
// virtualLinkPublic is true off-page, since search engines index this
// data publicly regardless of on-page visibility.
function useEventStructuredData(event, canonicalUrl) {
  useEffect(() => {
    if (!event) return
    const startDateTime = event.startTime ? `${event.date}T${event.startTime}` : event.date
    const endDateTime = event.endTime ? `${event.endDate || event.date}T${event.endTime}` : event.endDate || undefined
    const data = {
      '@context': 'https://schema.org',
      '@type': 'Event',
      name: event.title,
      description: event.shortDescription || event.title,
      ...(event.coverImage ? { image: resolveImage(event.coverImage, { width: 1200, height: 630 }) } : {}),
      startDate: startDateTime,
      ...(endDateTime ? { endDate: endDateTime } : {}),
      eventStatus: event.isCancelled ? 'https://schema.org/EventCancelled' : 'https://schema.org/EventScheduled',
      ...(event.format ? { eventAttendanceMode: ATTENDANCE_MODE[event.format] } : {}),
      ...(event.organizer
        ? { organizer: { '@type': 'Organization', name: event.organizer } }
        : { organizer: { '@type': 'Organization', name: 'Women Shaping Futures' } }),
      location:
        event.format === 'virtual'
          ? { '@type': 'VirtualLocation', url: canonicalUrl }
          : {
              '@type': 'Place',
              name: event.venue || undefined,
              address: {
                '@type': 'PostalAddress',
                ...(event.address ? { streetAddress: event.address } : {}),
                ...(event.location ? { addressLocality: event.location } : {}),
                ...(event.country ? { addressCountry: event.country.code } : {}),
              },
            },
      ...(event.registrationUrl
        ? {
            offers: {
              '@type': 'Offer',
              url: event.registrationUrl,
              price: event.ticketPrice || 0,
              priceCurrency: event.currency || 'USD',
              availability: event.soldOut ? 'https://schema.org/SoldOut' : 'https://schema.org/InStock',
            },
          }
        : {}),
    }
    let el = document.head.querySelector('script[data-event-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-event-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [event, canonicalUrl])
}

export default function EventDetailPage() {
  const { slug } = useParams()
  const [event, setEvent] = useState(undefined)
  const [speakers, setSpeakers] = useState([])
  const [sponsors, setSponsors] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setEvent(undefined)
    setSpeakers([])
    setSponsors([])
    setError(null)

    fetchEventBySlug(slug)
      .then((data) => {
        if (!active) return
        setEvent(data)
        if (!data) return

        Promise.all((data.speakers || []).map((s) => fetchPersonBySlug(s).catch(() => null)))
          .then((people) => active && setSpeakers(people.filter(Boolean)))
          .catch(() => {})

        Promise.all((data.sponsors || []).map((s) => fetchOrganizationBySlug(s).catch(() => null)))
          .then((orgs) => active && setSponsors(orgs.filter(Boolean)))
          .catch(() => {})
      })
      .catch(() => active && setError('Something went wrong loading this event. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = `https://womenshapingfutures.org/events/${slug}`

  useSeo(
    event
      ? {
          title: event.seo?.title || `${event.title} | Women Shaping Futures Events`,
          description: event.seo?.description || event.shortDescription,
          canonical: event.seo?.canonical || canonicalUrl,
          image: event.coverImage ? resolveImage(event.coverImage, { width: 1200, height: 630 }) : undefined,
          robots: event.seo?.robots,
        }
      : {},
  )

  useEventStructuredData(event, canonicalUrl)

  function handleRegisterClick() {
    trackEvent('event_registration_click', { eventSlug: event.slug })
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this event" description={error} /></div>
  if (event === undefined) return <PageLoader />
  if (event === null) return <NotFoundPage />

  const registrationClosed = event.isCancelled || event.soldOut || (event.registrationDeadline && event.registrationDeadline < new Date().toISOString().slice(0, 10))
  const canRegister = event.registrationRequired ? Boolean(event.registrationUrl) && !registrationClosed : !event.isCancelled
  const dateLine = event.endDate && event.endDate !== event.date
    ? `${formatDate(event.date, { month: 'long', day: 'numeric' })} – ${formatDate(event.endDate, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}`
    : formatDate(event.date, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })

  return (
    <div>
      <div className="relative">
        <MediaImage media={event.coverMedia} variant="hero" mediaPath={event.coverImage} alt={event.title} width={1920} height={720} aspect={2.6} tone="burgundy" priority className="h-64 w-full object-cover sm:h-96" />
        <div className="absolute inset-0 bg-gradient-to-t from-charcoal-800/80 to-transparent" />
        <div className="container-editorial absolute inset-x-0 bottom-0 pb-8 text-ivory">
          <Breadcrumb items={[{ label: 'Events', to: '/events' }, { label: event.title }]} />
          {event.type && <p className="eyebrow mt-3 !text-blush-200">{event.type}</p>}
          <h1 className="mt-1 font-serif text-3xl font-semibold sm:text-4xl">{event.title}</h1>
        </div>
      </div>

      <div className="container-editorial pt-6">
        {event.sponsored && (
          <div className="inline-flex items-center gap-2 border border-dashed border-taupe-300 bg-blush-50 px-4 py-2 text-xs text-charcoal-600">
            <span className="font-semibold uppercase tracking-wide text-burgundy-600">Sponsored</span>
            <span>This event is a paid placement{event.organizer ? ` from ${event.organizer}` : ''}.</span>
          </div>
        )}
        {event.isCancelled && (
          <div className="mt-4 flex items-center gap-2 border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <AlertCircle size={16} className="shrink-0" />
            <span className="font-semibold">Event cancelled</span> — this event is no longer taking place.
          </div>
        )}
      </div>

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          {event.shortDescription && <p className="text-lg leading-relaxed text-charcoal-600">{event.shortDescription}</p>}

          <ArticleContent blocks={event.description} />

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

          {event.format !== 'in-person' && event.virtualLink && event.virtualLinkPublic && (
            <div className="mt-10 border border-taupe-200 bg-cream p-5">
              <p className="text-sm font-semibold text-charcoal">Join online</p>
              <a href={event.virtualLink} target="_blank" rel="noreferrer" onClick={handleRegisterClick} className="mt-2 inline-block break-all text-sm text-burgundy-600 hover:underline">
                {event.virtualLink}
              </a>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <div className="border border-taupe-200 p-5">
            <ul className="space-y-4 text-sm text-charcoal-600">
              <li className="flex items-start gap-2">
                <Calendar size={16} className="mt-0.5 shrink-0" />
                <span>
                  {dateLine}
                  {event.startTime && (
                    <>
                      , {event.startTime}
                      {event.endTime ? `–${event.endTime}` : ''}
                      {event.timezone ? ` ${event.timezone}` : ''}
                    </>
                  )}
                </span>
              </li>
              {event.format !== 'virtual' && (event.venue || event.location) && (
                <li className="flex items-start gap-2">
                  <MapPin size={16} className="mt-0.5 shrink-0" />
                  {event.venue ? `${event.venue}${event.location ? `, ${event.location}` : ''}` : event.location}
                </li>
              )}
              {(event.format === 'virtual' || event.format === 'hybrid') && (
                <li className="flex items-start gap-2">
                  <Globe2 size={16} className="mt-0.5 shrink-0" />
                  Online{event.format === 'hybrid' ? ' + in person' : ''}
                </li>
              )}
              {event.timezone && !event.startTime && (
                <li className="flex items-start gap-2">
                  <Clock size={16} className="mt-0.5 shrink-0" />
                  {event.timezone}
                </li>
              )}
              <li className="flex items-start gap-2">
                <Ticket size={16} className="mt-0.5 shrink-0" />
                {event.soldOut ? 'Sold out' : formatCurrency(event.ticketPrice, event.currency)}
              </li>
              {event.registrationDeadline && !registrationClosed && (
                <li className="text-xs text-charcoal-600/70">Register by {formatDate(event.registrationDeadline)}</li>
              )}
            </ul>

            {canRegister ? (
              <a href={event.registrationUrl} target="_blank" rel="noreferrer" onClick={handleRegisterClick} className="btn-primary mt-5 flex w-full">
                {event.ticketPrice ? 'Get tickets' : 'Register free'}
              </a>
            ) : (
              <button type="button" disabled className="btn-secondary mt-5 flex w-full cursor-not-allowed justify-center opacity-60">
                {event.isCancelled ? 'Event cancelled' : event.soldOut ? 'Sold out' : registrationClosed ? 'Registration closed' : 'Registration unavailable'}
              </button>
            )}
            {event.registrationInstructions && !registrationClosed && (
              <p className="mt-3 text-xs text-charcoal-600">{event.registrationInstructions}</p>
            )}
          </div>

          {event.organizer && (
            <div className="border border-taupe-200 p-5">
              <p className="eyebrow mb-3">Hosted by</p>
              {event.organizerSlug ? (
                <Link to={`/organizations/${event.organizerSlug}`} className="flex items-center gap-3 font-serif text-base font-semibold text-charcoal hover:text-burgundy-600">
                  {event.organizerLogo && (
                    <MediaImage media={event.organizerLogoMedia} variant="thumbnail" mediaPath={event.organizerLogo} alt={event.organizer} width={80} height={80} aspect={1} className="h-8 w-8 object-contain" />
                  )}
                  {event.organizer}
                </Link>
              ) : (
                <p className="font-serif text-base font-semibold text-charcoal">{event.organizer}</p>
              )}
            </div>
          )}

          {sponsors.length > 0 && (
            <div>
              <p className="eyebrow mb-3">Sponsored by</p>
              <div className="flex flex-wrap gap-4">
                {sponsors.map((s) => (
                  <MediaImage key={s.slug} media={s.logoMedia} variant="thumbnail" mediaPath={s.logo} alt={s.name} width={140} height={70} aspect={2} tone="taupe" className="h-9 w-auto" />
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
