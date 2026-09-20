import { jobs } from '../../mock/jobs'
import JobCard from '../cards/JobCard'
import SectionHeading from '../ui/SectionHeading'

export default function JobsModule({ module }) {
  const items = [...jobs].filter((j) => j.featured).slice(0, module.itemCount || 4)
  return (
    <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow="Careers" heading={module.heading} subheading={module.subheading} viewAllHref="/jobs" />
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {items.map((j) => (
            <JobCard key={j.id} job={j} />
          ))}
        </div>
      </div>
    </section>
  )
}
