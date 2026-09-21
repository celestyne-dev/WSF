import { useState, useMemo } from 'react'
import { events } from '../mock/events'
import { getEventsFilterOptions } from '../api/events'
import { matchesCountry, matchesRegion } from '../mock/geography'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import EventCard from '../components/cards/EventCard'
import EmptyState from '../components/ui/EmptyState'

export default function EventsListingPage() {
  const [format, setFormat] = useState('')
  const [region, setRegion] = useState('')
  const [country, setCountry] = useState('')
  const options = useMemo(() => getEventsFilterOptions(), [])

  useSeo({
    title: 'Events | Women Shaping Futures',
    description: 'WSF conferences, webinars, and networking events — in person and online, worldwide.',
    canonical: 'https://womenshapingfutures.org/events',
  })

  const filtered = events.filter(
    (e) =>
      (!format || e.format === format) &&
      (!country || matchesCountry(e.countryCode, country)) &&
      (!region || matchesRegion(e.countryCode, region)),
  )

  return (
    <div>
      <PageHeader eyebrow="Join Us" title="Events" description="Conferences, workshops, and networking — hosted by Women Shaping Futures and our partners around the world." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Format" value={format} onChange={setFormat} options={options.formats} />
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
        </div>

        {filtered.length ? (
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {filtered.map((e) => (
              <EventCard key={e.id} event={e} />
            ))}
          </div>
        ) : (
          <div className="mt-8">
            <EmptyState title="No events match those filters" />
          </div>
        )}
      </div>
    </div>
  )
}
