import { resources } from '../mock/resources'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import ResourceCard from '../components/cards/ResourceCard'

export default function ShopPage() {
  const premium = resources.filter((r) => r.isPremium)

  useSeo({
    title: 'Shop | Women Shaping Futures',
    description: 'Digital products, templates, workbooks, and guides from Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/shop',
  })

  return (
    <div>
      <PageHeader eyebrow="Shop" title="WSF Shop" description="Digital templates, workbooks, and guides. Event tickets and memberships launching soon." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {premium.map((r) => (
            <ResourceCard key={r.id} resource={r} />
          ))}
        </div>
      </div>
    </div>
  )
}
