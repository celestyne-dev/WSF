import { useEffect, useState } from 'react'
import { fetchResources } from '../api/resources'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import ResourceCard from '../components/cards/ResourceCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

export default function ShopPage() {
  const [premium, setPremium] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Shop | Women Shaping Futures',
    description: 'Digital products, templates, workbooks, and guides from Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/shop',
  })

  useEffect(() => {
    let active = true
    fetchResources({ premium: 'premium', pageSize: 100 })
      .then((res) => active && setPremium(res.items))
      .catch(() => active && setError('Something went wrong loading the shop. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <PageHeader eyebrow="Shop" title="WSF Shop" description="Digital templates, workbooks, and guides. Event tickets and memberships launching soon." />
      <div className="container-editorial py-14">
        {error && <EmptyState title="Couldn't load the shop" description={error} />}
        {!error && premium === null && <PageLoader />}
        {!error && premium !== null && (
          premium.length ? (
            <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {premium.map((r) => (
                <ResourceCard key={r.id} resource={r} />
              ))}
            </div>
          ) : (
            <EmptyState title="Nothing in the shop yet" description="Check back soon for new templates, workbooks, and guides." />
          )
        )}
      </div>
    </div>
  )
}
