import { useState, useEffect } from 'react'
import { fetchPeople, fetchPeopleFilterOptions } from '../api/people'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import PersonCard from '../components/cards/PersonCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

const EMPTY_OPTIONS = { countries: [], regions: [], industries: [], expertise: [] }

export default function PeopleDirectoryPage() {
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
  const [industry, setIndustry] = useState('')
  const [expertise, setExpertise] = useState('')
  const [people, setPeople] = useState(null)
  const [error, setError] = useState(null)
  const [options, setOptions] = useState(EMPTY_OPTIONS)

  useEffect(() => {
    let active = true
    fetchPeopleFilterOptions().then((opts) => {
      if (active) setOptions(opts)
    })
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: 'People Directory | Women Shaping Futures',
    description: 'Discover the women leading business, science, government, and culture around the world.',
    canonical: 'https://womenshapingfutures.org/people',
  })

  useEffect(() => {
    let active = true
    setPeople(null)
    setError(null)
    fetchPeople({ country, region, industry, pageSize: 100 })
      .then((res) => {
        if (active) setPeople(res.items)
      })
      .catch(() => {
        if (active) setError('Something went wrong loading the People Directory. Please try again.')
      })
    return () => {
      active = false
    }
  }, [country, region, industry])

  const filtered = (people || []).filter((p) => !expertise || p.expertise.includes(expertise))

  return (
    <div>
      <PageHeader eyebrow="People" title="The People Directory" description="Founders, executives, scientists, and public servants — the women building the future, profiled by WSF, from every region." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
          <FilterSelect label="Industry" value={industry} onChange={setIndustry} options={options.industries} />
          <FilterSelect label="Expertise" value={expertise} onChange={setExpertise} options={options.expertise} />
        </div>

        {error && (
          <div className="mt-10">
            <EmptyState title="Couldn't load the directory" description={error} />
          </div>
        )}

        {!error && people === null && <PageLoader />}

        {!error && people !== null && (
          filtered.length ? (
            <div className="mt-10 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-4">
              {filtered.map((person) => (
                <PersonCard key={person.id} person={person} />
              ))}
            </div>
          ) : (
            <div className="mt-10">
              <EmptyState title="No one matches those filters yet" description="Try broadening your search, or check back as we add new profiles every week." />
            </div>
          )
        )}
      </div>
    </div>
  )
}
