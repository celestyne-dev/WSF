import { useEffect, useState } from 'react'
import { fetchResources } from '../../api/resources'
import ResourceCard from '../cards/ResourceCard'
import SectionHeading from '../ui/SectionHeading'

export default function ResourcesModule({ module }) {
  const [items, setItems] = useState([])

  useEffect(() => {
    let active = true
    fetchResources({ featured: true, pageSize: module.itemCount || 3 })
      .then((res) => active && setItems(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [module.itemCount])

  return (
    <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow="Resource Library" heading={module.heading} subheading={module.subheading} viewAllHref="/resources" />
        <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-3">
          {items.map((r) => (
            <ResourceCard key={r.id} resource={r} />
          ))}
        </div>
      </div>
    </section>
  )
}
