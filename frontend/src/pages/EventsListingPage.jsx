import { useEffect, useState } from 'react'
import { fetchEvents, fetchEventsFilterOptions } from '../api/events'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import EventCard from '../components/cards/EventCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

export default function EventsListingPage() {
  const [format, setFormat] = useState('')
  const [region, setRegion] = useState('')
  const [country, setCountry] = useState('')
  const [events, setEvents] = useState(null)
  const [options, setOptions] = useState({ formats: [], countries: [], regions: [] })
  const [error, setError] = useState(null)

  useSeo({
    title: 'Events | Women Shaping Futures',
    description: 'WSF conferences, webinars, and networking events — in person and online, worldwide.',
    canonical: 'https://womenshapingfutures.org/events',
  })

  useEffect(() => {
    let active = true
    fetchEventsFilterOptions()
      .then((data) => active && setOptions(data))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchEvents({ format, country, region, pageSize: 100 })
      .then((res) => active && setEvents(res.items))
      .catch(() => active && setError('Something went wrong loading events. Please try again.'))
    return () => {
      active = false
    }
  }, [format, country, region])

  return (
    <div>
      <PageHeader eyebrow="Join Us" title="Events" description="Conferences, workshops, and networking — hosted by Women Shaping Futures and our partners around the world." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Format" value={format} onChange={setFormat} options={options.formats} />
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
        </div>

        {error && (
          <div className="mt-8">
            <EmptyState title="Couldn't load events" description={error} />
          </div>
        )}
        {!error && events === null && <PageLoader />}
        {!error && events !== null && (
          events.length ? (
            <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {events.map((e) => (
                <EventCard key={e.id} event={e} />
              ))}
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState title="No events match those filters" />
            </div>
          )
        )}
      </div>
    </div>
  )
}
