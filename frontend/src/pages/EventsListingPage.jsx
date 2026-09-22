import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchEvents, fetchEventsFilterOptions } from '../api/events'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import EventCard from '../components/cards/EventCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

const PRICE_OPTIONS = [
  { value: 'free', label: 'Free' },
  { value: 'paid', label: 'Paid' },
]

export default function EventsListingPage() {
  const [query, setQuery] = useState('')
  const [format, setFormat] = useState('')
  const [type, setType] = useState('')
  const [region, setRegion] = useState('')
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [organizer, setOrganizer] = useState('')
  const [price, setPrice] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [when, setWhen] = useState('upcoming')
  const [featured, setFeatured] = useState(null)
  const [events, setEvents] = useState(null)
  const [options, setOptions] = useState({ types: [], formats: [], countries: [], regions: [], organizers: [] })
  const [error, setError] = useState(null)

  useSeo({
    title: 'Events | Women Shaping Futures',
    description: 'WSF conferences, webinars, workshops, and networking events — in person and online, worldwide.',
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

  const hasFilters = query || format || type || region || country || city || organizer || price || dateFrom || dateTo

  useEffect(() => {
    let active = true
    // Featured events are shown as their own section only on the default,
    // unfiltered view — once someone searches or filters, a single
    // results grid is clearer than splitting matches across sections.
    fetchEvents({ pageSize: 12, featured: 'true', when: 'upcoming' })
      .then((res) => active && setFeatured(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchEvents({ query, format, type, country, region, city, organizer, price, dateFrom, dateTo, when, pageSize: 100 })
      .then((res) => active && setEvents(res.items))
      .catch(() => active && setError('Something went wrong loading events. Please try again.'))
    return () => {
      active = false
    }
  }, [query, format, type, country, region, city, organizer, price, dateFrom, dateTo, when])

  return (
    <div>
      <PageHeader eyebrow="Join Us" title="Events" description="Conferences, workshops, and networking — hosted by Women Shaping Futures and our partners around the world." />

      {!hasFilters && featured && featured.length > 0 && (
        <div className="border-b border-taupe-200 bg-blush-50/40 py-10">
          <div className="container-editorial">
            <p className="eyebrow mb-5">Featured</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {featured.slice(0, 4).map((e) => (
                <EventCard key={e.id} event={e} />
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-center gap-2 border-b border-taupe-200 pb-4">
          <button
            type="button"
            onClick={() => setWhen('upcoming')}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wide ${when === 'upcoming' ? 'bg-burgundy-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
          >
            Upcoming
          </button>
          <button
            type="button"
            onClick={() => setWhen('past')}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wide ${when === 'past' ? 'bg-burgundy-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
          >
            Past events
          </button>
        </div>
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 py-8">
          <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
            <Search size={15} className="text-charcoal-600" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search events…" className="w-52 text-sm focus:outline-none" />
          </div>
          <FilterSelect label="Type" value={type} onChange={setType} options={options.types} />
          <FilterSelect label="Format" value={format} onChange={setFormat} options={options.formats} />
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
          <FilterSelect label="Price" value={price} onChange={setPrice} options={PRICE_OPTIONS} />
          {options.organizers?.length > 0 && <FilterSelect label="Organizer" value={organizer} onChange={setOrganizer} options={options.organizers} />}
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            City
            <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Any city" className="min-w-[9rem] border border-taupe-300 bg-white px-3 py-2 text-sm font-normal normal-case text-charcoal focus:border-burgundy-500 focus:outline-none" />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            From
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm font-normal normal-case text-charcoal focus:border-burgundy-500 focus:outline-none" />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            To
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm font-normal normal-case text-charcoal focus:border-burgundy-500 focus:outline-none" />
          </label>
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
              <EmptyState title={when === 'past' ? 'No past events match those filters' : 'No upcoming events match those filters'} description="Try broadening your search or clearing a filter." />
            </div>
          )
        )}
      </div>
    </div>
  )
}
