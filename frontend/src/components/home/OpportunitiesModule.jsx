import { useEffect, useState } from 'react'
import { fetchOpportunities } from '../../api/opportunities'
import OpportunityCard from '../cards/OpportunityCard'
import SectionHeading from '../ui/SectionHeading'

export default function OpportunitiesModule({ module }) {
  const [items, setItems] = useState([])

  useEffect(() => {
    let active = true
    fetchOpportunities({ featured: true, pageSize: module.itemCount || 3 })
      .then((res) => active && setItems(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [module.itemCount])

  return (
    <section className="py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow="Opportunity" heading={module.heading} subheading={module.subheading} viewAllHref="/opportunities" />
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {items.map((o) => (
            <OpportunityCard key={o.id} opportunity={o} />
          ))}
        </div>
      </div>
    </section>
  )
}
