import { useState, useMemo } from 'react'
import { people } from '../mock/people'
import { getPeopleFilterOptions } from '../api/people'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import PersonCard from '../components/cards/PersonCard'
import EmptyState from '../components/ui/EmptyState'

export default function PeopleDirectoryPage() {
  const [country, setCountry] = useState('')
  const [industry, setIndustry] = useState('')
  const [expertise, setExpertise] = useState('')
  const options = useMemo(() => getPeopleFilterOptions(), [])

  useSeo({
    title: 'People Directory | Women Shaping Futures',
    description: 'Discover the women leading business, science, government, and culture across Africa and the diaspora.',
    canonical: 'https://womenshapingfutures.org/people',
  })

  const filtered = people.filter(
    (p) =>
      (!country || p.country === country) &&
      (!industry || p.industry === industry) &&
      (!expertise || p.expertise.includes(expertise)),
  )

  return (
    <div>
      <PageHeader eyebrow="People" title="The People Directory" description="Founders, executives, scientists, and public servants — the women building the future, profiled by WSF." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
          <FilterSelect label="Industry" value={industry} onChange={setIndustry} options={options.industries} />
          <FilterSelect label="Expertise" value={expertise} onChange={setExpertise} options={options.expertise} />
        </div>

        {filtered.length ? (
          <div className="mt-10 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-4">
            {filtered.map((person) => (
              <PersonCard key={person.id} person={person} />
            ))}
          </div>
        ) : (
          <div className="mt-10">
            <EmptyState title="No one matches those filters yet" description="Try broadening your search, or check back as we add new profiles every week." />
          </div>
        )}
      </div>
    </div>
  )
}
