import { useEffect, useState } from 'react'
import { fetchSeries } from '../api/taxonomies'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import PageHeader from '../components/ui/PageHeader'
import SeriesCard from '../components/cards/SeriesCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

const CANONICAL = 'https://womenshapingfutures.org/series'

export default function SeriesIndexPage() {
  const [series, setSeries] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Editorial Series | Women Shaping Futures',
    description: 'Explore our ongoing editorial series, from Women Doing Incredible Things to Founder Stories.',
    canonical: CANONICAL,
  })
  // Home > Series — matches the server's own 2-level breadcrumb for this
  // list page; finds and reuses the server-rendered tag, removes it on
  // navigating away.
  useBreadcrumbStructuredData([{ label: 'Series' }], CANONICAL)

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
