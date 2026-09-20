import { events } from '../../mock/events'
import EventCard from '../cards/EventCard'
import SectionHeading from '../ui/SectionHeading'

export default function EventsModule({ module }) {
  const items = [...events].slice(0, module.itemCount || 3)
  return (
    <section className="py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow="Join Us" heading={module.heading} subheading={module.subheading} viewAllHref="/events" />
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {items.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </div>
      </div>
    </section>
  )
}
