import { useEffect, useState } from 'react'
import { fetchSeries } from '../api/taxonomies'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import SeriesCard from '../components/cards/SeriesCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

export default function SeriesIndexPage() {
  const [series, setSeries] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Editorial Series | Women Shaping Futures',
    description: 'Explore our ongoing editorial series, from Women Doing Incredible Things to Founder Stories.',
    canonical: 'https://womenshapingfutures.org/series',
  })

  useEffect(() => {
    let active = true
    fetchSeries()
      .then((data) => active && setSeries(data))
      .catch(() => active && setError('Something went wrong loading our series. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <PageHeader eyebrow="Series" title="Editorial Series" description="Ongoing collections of stories built around a single theme, question, or kind of woman we can't stop covering." />
      <div className="container-editorial py-14">
        {error && <EmptyState title="Couldn't load series" description={error} />}
        {!error && series === null && <PageLoader />}
        {!error && series !== null && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {series.map((item) => (
              <SeriesCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
