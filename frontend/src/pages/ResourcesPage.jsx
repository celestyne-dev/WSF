import { useState } from 'react'
import { resources } from '../mock/resources'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import ResourceCard from '../components/cards/ResourceCard'

export default function ResourcesPage() {
  const [type, setType] = useState('')
  const [premium, setPremium] = useState('')

  useSeo({
    title: 'Resource Library | Women Shaping Futures',
    description: 'Guides, templates, and worksheets to help you plan your career, negotiate pay, and grow a business.',
    canonical: 'https://womenshapingfutures.org/resources',
  })

  const types = [...new Set(resources.map((r) => r.type))]
  const filtered = resources.filter(
    (r) => (!type || r.type === type) && (!premium || (premium === 'free' ? !r.isPremium : r.isPremium)),
  )

  return (
    <div>
      <PageHeader eyebrow="Resource Library" title="Guides, Templates & Worksheets" description="Practical tools built by our editors and career coaches — free and premium." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Type" value={type} onChange={setType} options={types} />
          <FilterSelect label="Access" value={premium} onChange={setPremium} options={['free', 'premium']} />
        </div>
        <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((r) => (
            <ResourceCard key={r.id} resource={r} />
          ))}
        </div>
      </div>
    </div>
  )
}
