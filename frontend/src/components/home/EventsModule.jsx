import { useEffect, useState } from 'react'
import { fetchEvents } from '../../api/events'
import EventCard from '../cards/EventCard'
import SectionHeading from '../ui/SectionHeading'

export default function EventsModule({ module }) {
  const [items, setItems] = useState([])

  useEffect(() => {
    let active = true
    fetchEvents({ pageSize: module.itemCount || 3 })
      .then((res) => active && setItems(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [module.itemCount])

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
