import { useEffect, useState } from 'react'
import { fetchEvents } from '../../api/events'
import EventCard from '../cards/EventCard'
import SectionHeading from '../ui/SectionHeading'

export default function EventsModule({ module }) {
  const [items, setItems] = useState([])
  // 'loading' | 'error' | 'success' — only a confirmed successful fetch
  // that came back empty hides the section; a slow or failed fetch keeps
  // rendering the section exactly as before (no flash of "nothing here"
  // while still loading, and an error is never treated as empty).
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let active = true
    fetchEvents({ pageSize: module.itemCount || 3 })
      .then((res) => {
        if (!active) return
        setItems(res.items)
        setStatus('success')
      })
      .catch(() => active && setStatus('error'))
    return () => {
      active = false
    }
  }, [module.itemCount])

  if (status === 'success' && items.length === 0) return null

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
