import { useEffect, useState } from 'react'
import { fetchJobs } from '../../api/jobs'
import JobCard from '../cards/JobCard'
import SectionHeading from '../ui/SectionHeading'

export default function JobsModule({ module }) {
  const [items, setItems] = useState([])

  useEffect(() => {
    let active = true
    fetchJobs({ featured: true, pageSize: module.itemCount || 4 })
      .then((res) => active && setItems(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [module.itemCount])

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
