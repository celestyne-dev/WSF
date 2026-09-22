import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchJobs, fetchJobsFilterOptions } from '../api/jobs'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import JobCard from '../components/cards/JobCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

const PAGE_SIZE = 10
const CLOSING_OPTIONS = [
  { value: '7', label: 'Within 7 days' },
  { value: '30', label: 'Within 30 days' },
]

export default function JobsListingPage() {
  const [query, setQuery] = useState('')
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
  const [city, setCity] = useState('')
  const [industry, setIndustry] = useState('')
  const [workMode, setWorkMode] = useState('')
  const [careerLevel, setCareerLevel] = useState('')
  const [employmentType, setEmploymentType] = useState('')
  const [company, setCompany] = useState('')
  const [salaryMin, setSalaryMin] = useState('')
  const [closingWithinDays, setClosingWithinDays] = useState('')
  const [page, setPage] = useState(1)

  const [featuredJobs, setFeaturedJobs] = useState(null)
  const [jobs, setJobs] = useState(null)
  const [meta, setMeta] = useState(null)
  const [options, setOptions] = useState({ countries: [], regions: [], industries: [], workModes: [], careerLevels: [], employmentTypes: [], companies: [] })
  const [error, setError] = useState(null)

  useSeo({
    title: 'Jobs for Women | Women Shaping Futures',
    description: 'Curated job openings from employers committed to hiring and advancing women, worldwide and remote.',
    canonical: 'https://womenshapingfutures.org/jobs',
  })

  useEffect(() => {
    let active = true
    fetchJobsFilterOptions()
      .then((data) => active && setOptions(data))
      .catch(() => {})
    fetchJobs({ featured: true, pageSize: 3 })
      .then((res) => active && setFeaturedJobs(res.items))
      .catch(() => active && setFeaturedJobs([]))
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    setPage(1)
  }, [query, country, region, city, industry, workMode, careerLevel, employmentType, company, salaryMin, closingWithinDays])

  useEffect(() => {
    let active = true
    setError(null)
    fetchJobs({
      query,
      country,
      region,
      city,
      industry,
      workMode,
      careerLevel,
      employmentType,
      organization: company,
      salaryMin,
      closingWithinDays,
      page,
      pageSize: PAGE_SIZE,
    })
      .then((res) => {
        if (!active) return
        setJobs(res.items)
        setMeta(res.pagination)
      })
      .catch(() => active && setError('Something went wrong loading jobs. Please try again.'))
    return () => {
      active = false
    }
  }, [query, country, region, city, industry, workMode, careerLevel, employmentType, company, salaryMin, closingWithinDays, page])

  const hasFilters = query || country || region || city || industry || workMode || careerLevel || employmentType || company || salaryMin || closingWithinDays

  return (
    <div>
      <PageHeader eyebrow="Opportunity" title="Jobs" description="Roles from employers we've vetted for pay transparency and growth potential — worldwide, remote, and hybrid. New listings added weekly." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Search
            <div className="flex min-w-[14rem] items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
              <Search size={15} className="text-charcoal-600" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Job title or company…" className="w-full text-sm font-normal normal-case text-charcoal focus:outline-none" />
            </div>
          </div>
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
          <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            City
            <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Any city" className="min-w-[9rem] border border-taupe-300 bg-white px-3 py-2 text-sm font-normal normal-case text-charcoal focus:border-burgundy-500 focus:outline-none" />
          </div>
          <FilterSelect label="Work Mode" value={workMode} onChange={setWorkMode} options={options.workModes} />
          <FilterSelect label="Industry" value={industry} onChange={setIndustry} options={options.industries} />
          <FilterSelect label="Employment Type" value={employmentType} onChange={setEmploymentType} options={options.employmentTypes} />
          <FilterSelect label="Career Level" value={careerLevel} onChange={setCareerLevel} options={options.careerLevels} />
          {options.companies?.length > 0 && <FilterSelect label="Company" value={company} onChange={setCompany} options={options.companies} />}
          <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Min. salary
            <input type="number" value={salaryMin} onChange={(e) => setSalaryMin(e.target.value)} placeholder="Any" className="min-w-[7rem] border border-taupe-300 bg-white px-3 py-2 text-sm font-normal normal-case text-charcoal focus:border-burgundy-500 focus:outline-none" />
          </div>
          <FilterSelect label="Closing" value={closingWithinDays} onChange={setClosingWithinDays} options={CLOSING_OPTIONS} />
        </div>

        {featuredJobs?.length > 0 && !hasFilters && (
          <div className="mt-8">
            <p className="eyebrow mb-4">Featured roles</p>
            <div className="grid grid-cols-1 gap-4">
              {featuredJobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="mt-8">
            <EmptyState title="Couldn't load jobs" description={error} />
          </div>
        )}
        {!error && jobs === null && <PageLoader />}
        {!error && jobs !== null && (
          jobs.length ? (
            <div className="mt-8">
              {featuredJobs?.length > 0 && !hasFilters && <p className="eyebrow mb-4">Latest roles</p>}
              <div className="grid grid-cols-1 gap-4">
                {jobs.map((job) => (
                  <JobCard key={job.id} job={job} />
                ))}
              </div>
              {meta && meta.totalPages > 1 && (
                <div className="mt-8 flex items-center justify-center gap-4">
                  <button
                    type="button"
                    disabled={meta.page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                    Page {meta.page} of {meta.totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={meta.page >= meta.totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState title="No jobs match those filters" description="Try clearing a filter, or check back soon — we add new roles every week." />
            </div>
          )
        )}
      </div>
    </div>
  )
}
