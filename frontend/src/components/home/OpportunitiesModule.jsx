import { useEffect, useState } from 'react'
import { fetchOpportunities } from '../../api/opportunities'
import OpportunityCard from '../cards/OpportunityCard'
import SectionHeading from '../ui/SectionHeading'

export default function OpportunitiesModule({ module }) {
  const [items, setItems] = useState([])
  // 'loading' | 'error' | 'success' — only a confirmed successful fetch
  // that came back empty hides the section; a slow or failed fetch keeps
  // rendering the section exactly as before (no flash of "nothing here"
  // while still loading, and an error is never treated as empty).
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let active = true
    fetchOpportunities({ featured: true, pageSize: module.itemCount || 3 })
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
