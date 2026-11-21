import { useEffect, useState } from 'react'
import { fetchJobs, mapJob } from '../../api/jobs'
import JobCard from '../cards/JobCard'
import SectionHeading from '../ui/SectionHeading'

export default function JobsModule({ module }) {
  // Hard load of "/": the server already fetched this (module.initialData).
  const initial = module.initialData?.items
  const [items, setItems] = useState(() => (initial ? initial.map(mapJob) : []))
  // 'loading' | 'error' | 'success' — only a confirmed successful fetch
  // that came back empty hides the section; a slow or failed fetch keeps
  // rendering the section exactly as before (no flash of "nothing here"
  // while still loading, and an error is never treated as empty).
  const [status, setStatus] = useState(initial ? 'success' : 'loading')

  useEffect(() => {
    if (initial) return undefined
    let active = true
    fetchJobs({ featured: true, pageSize: module.itemCount || 4 })
      .then((res) => {
        if (!active) return
        setItems(res.items)
        setStatus('success')
      })
      .catch(() => active && setStatus('error'))
    return () => {
      active = false
    }
  }, [module.itemCount, initial])

  if (status === 'success' && items.length === 0) return null

  return (
    <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow={module.sort === 'closing_soon' ? 'Closing soon' : 'Careers'} heading={module.heading} subheading={module.subheading} viewAllHref="/jobs" />
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {items.map((j) => (
            <JobCard key={j.id} job={j} />
          ))}
        </div>
      </div>
    </section>
  )
}
