import { events } from '../mock/events'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import EventCard from '../components/cards/EventCard'

export default function EventsListingPage() {
  useSeo({
    title: 'Events | Women Shaping Futures',
    description: 'WSF conferences, webinars, and networking events — in person and online.',
    canonical: 'https://womenshapingfutures.org/events',
  })

  return (
    <div>
      <PageHeader eyebrow="Join Us" title="Events" description="Conferences, workshops, and networking — hosted by Women Shaping Futures and our partners." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {events.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </div>
      </div>
    </div>
  )
}
