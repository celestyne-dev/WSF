import { opportunities } from '../../mock/opportunities'
import OpportunityCard from '../cards/OpportunityCard'
import SectionHeading from '../ui/SectionHeading'

export default function OpportunitiesModule({ module }) {
  const items = [...opportunities].filter((o) => o.featured).slice(0, module.itemCount || 3)
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
