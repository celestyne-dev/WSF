import { resources } from '../../mock/resources'
import ResourceCard from '../cards/ResourceCard'
import SectionHeading from '../ui/SectionHeading'

export default function ResourcesModule({ module }) {
  const items = [...resources].filter((r) => r.featured).slice(0, module.itemCount || 3)
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
