import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Calendar, MapPin, Clock, Ticket, Globe2, AlertCircle, CalendarPlus, PauseCircle } from 'lucide-react'
import { fetchEventBySlug, fetchEvents } from '../api/events'
import { formatDate, formatCurrency } from '../utils/format'
import { resolveImage } from '../utils/media'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ShareBar from '../components/ui/ShareBar'
import NewsletterForm from '../components/ui/NewsletterForm'
import EventCard from '../components/cards/EventCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

const ATTENDANCE_MODE = {
  'in-person': 'https://schema.org/OfflineEventAttendanceMode',
  virtual: 'https://schema.org/OnlineEventAttendanceMode',
  hybrid: 'https://schema.org/MixedEventAttendanceMode',
}

const EVENT_STATUS_SCHEMA = {
  cancelled: 'https://schema.org/EventCancelled',
  postponed: 'https://schema.org/EventPostponed',
}

// Valid schema.org Event structured data — built only from fields this
// event record actually carries. Nothing is fabricated to "complete" the
// schema; the private virtual join link is never included here even when
// virtualLinkPublic is true off-page, since search engines index this
// data publicly regardless of on-page visibility. Performers are only the
// speakers WSF actually lists for this event — never invented.
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
      eventStatus: EVENT_STATUS_SCHEMA[event.isCancelled ? 'cancelled' : event.isPostponed ? 'postponed' : null] || 'https://schema.org/EventScheduled',
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
                ...(event.city ? { addressLocality: event.city } : event.location ? { addressLocality: event.location } : {}),
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
      ...(event.speakers?.length
        ? { performer: event.speakers.map((s) => ({ '@type': 'Person', name: s.name })).filter((p) => p.name) }
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

function pad2(n) {
  return String(n).padStart(2, '0')
}

function toCalendarDateTime(dateStr, timeStr) {
  const compact = dateStr.replace(/-/g, '')
  if (!timeStr) return compact
  const [hh, mm] = timeStr.split(':')
  return `${compact}T${pad2(hh)}${pad2(mm)}00`
}

function calendarLocation(event) {
  if (event.format === 'virtual') return event.virtualLinkPublic ? event.virtualLink : 'Online — link sent to registered attendees'
  return [event.venue, event.location].filter(Boolean).join(', ')
}

function buildGoogleCalendarUrl(event) {
  const start = toCalendarDateTime(event.date, event.startTime)
  const end = toCalendarDateTime(event.endDate || event.date, event.endTime || event.startTime)
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: event.title,
    dates: `${start}/${end}`,
    details: event.shortDescription || '',
    location: calendarLocation(event),
  })
  if (event.timezone) params.set('ctz', event.timezone)
  return `https://calendar.google.com/calendar/render?${params.toString()}`
}

function downloadIcs(event, canonicalUrl) {
  const start = toCalendarDateTime(event.date, event.startTime)
  const end = toCalendarDateTime(event.endDate || event.date, event.endTime || event.startTime)
  const escapeIcs = (v) => String(v || '').replace(/,/g, '\\,').replace(/\n/g, ' ')
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Women Shaping Futures//Events//EN',
    'BEGIN:VEVENT',
    `UID:${event.slug}@womenshapingfutures.org`,
    `SUMMARY:${escapeIcs(event.title)}`,
    `DESCRIPTION:${escapeIcs(event.shortDescription)}`,
    `DTSTART:${start}`,
    `DTEND:${end}`,
    `LOCATION:${escapeIcs(calendarLocation(event))}`,
    `URL:${canonicalUrl}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ]
  const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${event.slug}.ics`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function SpeakerTile({ speaker }) {
  const content = (
    <>
      <MediaImage media={speaker.headshot} width={160} height={160} aspect={1} alt={speaker.name} tone="plum" className="h-20 w-20 rounded-full object-cover" />
      <div className="mt-2">
        <p className="font-serif text-sm font-semibold text-charcoal">{speaker.name}</p>
        {(speaker.title || speaker.organizationName) && (
          <p className="text-xs text-charcoal-600">{[speaker.title, speaker.organizationName].filter(Boolean).join(' · ')}</p>
        )}
      </div>
    </>
  )
  if (speaker.profileSlug) {
    return (
      <Link to={`/people/${speaker.profileSlug}`} className="group block text-center transition-colors hover:text-burgundy-600">
        {content}
      </Link>
    )
  }
  return <div className="text-center">{content}</div>
}

function SponsorTile({ sponsor }) {
  const inner = sponsor.logo?.mediaPath ? (
    <MediaImage media={sponsor.logo} variant="thumbnail" width={160} height={80} aspect={2} tone="taupe" alt={sponsor.name} className="h-10 w-auto object-contain" />
  ) : (
    <span className="font-serif text-sm font-semibold text-charcoal">{sponsor.name}</span>
  )
  const content = (
    <div className="flex flex-col items-start gap-1.5">
      {inner}
      {sponsor.tier && <span className="text-[10px] font-semibold uppercase tracking-wide text-charcoal-600/60">{sponsor.tier}</span>}
    </div>
  )
  if (sponsor.organizationSlug) {
    return (
      <Link to={`/organizations/${sponsor.organizationSlug}`} className="transition-opacity hover:opacity-80">
        {content}
      </Link>
    )
  }
  if (sponsor.url) {
    return (
      <a href={sponsor.url} target="_blank" rel="noreferrer" className="transition-opacity hover:opacity-80">
        {content}
      </a>
    )
  }
  return content
}

export default function EventDetailPage() {
  const { slug } = useParams()
  const [event, setEvent] = useState(undefined)
  const [related, setRelated] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setEvent(undefined)
    setRelated([])
    setError(null)

    fetchEventBySlug(slug)
      .then((data) => {
        if (!active) return
        setEvent(data)
        if (!data) return
        trackEvent('event_view', { eventSlug: data.slug })

        if (data.type) {
          fetchEvents({ type: data.type, when: 'upcoming', pageSize: 4 })
            .then((res) => active && setRelated(res.items.filter((e) => e.slug !== slug).slice(0, 3)))
            .catch(() => {})
        }
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

  function handleAddToCalendar() {
    trackEvent('event_add_to_calendar_click', { eventSlug: event.slug })
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this event" description={error} /></div>
  if (event === undefined) return <PageLoader />
  if (event === null) return <NotFoundPage />

  const registrationClosed = event.isCancelled || event.isPostponed || event.soldOut || (event.registrationDeadline && event.registrationDeadline < new Date().toISOString().slice(0, 10))
  const canRegister = event.registrationRequired ? Boolean(event.registrationUrl) && !registrationClosed : !event.isCancelled && !event.isPostponed
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
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {event.type && <p className="eyebrow !text-blush-200">{event.type}</p>}
            {event.isOngoing && <span className="inline-flex items-center gap-1 bg-emerald-500/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ivory">Happening now</span>}
          </div>
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
        {event.isPostponed && (
          <div className="mt-4 flex items-center gap-2 border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <PauseCircle size={16} className="shrink-0" />
            <span className="font-semibold">Event postponed</span> — a new date will be announced. Check back for updates.
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
                {event.agenda.map((item, i) => (
                  <li key={i} className="flex gap-6 py-4">
                    <span className="w-28 shrink-0 text-sm font-semibold text-burgundy-600">
                      {item.startTime}
                      {item.endTime ? `–${item.endTime}` : ''}
                    </span>
                    <div>
                      <p className="text-base font-medium text-charcoal">{item.title}</p>
                      {item.sessionType && <span className="text-xs uppercase tracking-wide text-charcoal-600/60">{item.sessionType}</span>}
                      {item.description && <p className="mt-1 text-sm text-charcoal-600">{item.description}</p>}
                      {item.speakerNames?.length > 0 && <p className="mt-1 text-xs text-charcoal-600/70">{item.speakerNames.join(', ')}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {event.speakers?.length > 0 && (
            <div className="mt-10">
              <h2 className="font-serif text-2xl font-semibold text-charcoal">Speakers</h2>
              <div className="mt-5 grid grid-cols-2 gap-6 sm:grid-cols-3">
                {event.speakers.map((s, i) => (
                  <SpeakerTile key={s.id ?? i} speaker={s} />
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

          <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-taupe-200 pt-6">
            <ShareBar title={event.title} url={canonicalUrl} trackEventName="event_share_click" trackPayload={{ eventSlug: event.slug }} />
          </div>
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
                {event.isCancelled ? 'Event cancelled' : event.isPostponed ? 'New date TBD' : event.soldOut ? 'Sold out' : registrationClosed ? 'Registration closed' : 'Registration unavailable'}
              </button>
            )}
            {event.registrationInstructions && !registrationClosed && (
              <p className="mt-3 text-xs text-charcoal-600">{event.registrationInstructions}</p>
            )}

            {!event.isCancelled && !event.isPostponed && !event.isPast && (
              <div className="mt-3 flex items-center justify-center gap-4 text-xs">
                <a href={buildGoogleCalendarUrl(event)} target="_blank" rel="noreferrer" onClick={handleAddToCalendar} className="inline-flex items-center gap-1 font-semibold text-charcoal-600 hover:text-burgundy-600">
                  <CalendarPlus size={13} /> Add to calendar
                </a>
                <button type="button" onClick={() => downloadIcs(event, canonicalUrl)} className="font-semibold text-charcoal-600 hover:text-burgundy-600">
                  Download .ics
                </button>
              </div>
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

          {event.sponsors?.length > 0 && (
            <div>
              <p className="eyebrow mb-3">Sponsored by</p>
              <div className="flex flex-wrap gap-5">
                {event.sponsors.map((s, i) => (
                  <SponsorTile key={s.id ?? i} sponsor={s} />
                ))}
              </div>
            </div>
          )}

          <div className="border border-taupe-200 bg-cream p-5">
            <NewsletterForm variant="light" source="event_detail" />
          </div>
        </aside>
      </div>

      {related.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">More {event.type ? `${event.type.toLowerCase()} events` : 'events'}</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((e) => (
              <EventCard key={e.id} event={e} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
