import { useEffect, useState } from 'react'
import { fetchJobs, fetchJobsFilterOptions } from '../api/jobs'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import JobCard from '../components/cards/JobCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

export default function JobsListingPage() {
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
  const [industry, setIndustry] = useState('')
  const [workMode, setWorkMode] = useState('')
  const [careerLevel, setCareerLevel] = useState('')
  const [employmentType, setEmploymentType] = useState('')
  const [jobs, setJobs] = useState(null)
  const [options, setOptions] = useState({ countries: [], regions: [], industries: [], workModes: [], careerLevels: [], employmentTypes: [] })
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
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchJobs({ country, region, industry, workMode, careerLevel, employmentType, pageSize: 100 })
      .then((res) => active && setJobs(res.items))
      .catch(() => active && setError('Something went wrong loading jobs. Please try again.'))
    return () => {
      active = false
    }
  }, [country, region, industry, workMode, careerLevel, employmentType])

  return (
    <div>
      <PageHeader eyebrow="Opportunity" title="Jobs" description="Roles from employers we've vetted for pay transparency and growth potential — worldwide, remote, and hybrid. New listings added weekly." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
          <FilterSelect label="Industry" value={industry} onChange={setIndustry} options={options.industries} />
          <FilterSelect label="Work Mode" value={workMode} onChange={setWorkMode} options={options.workModes} />
          <FilterSelect label="Employment Type" value={employmentType} onChange={setEmploymentType} options={options.employmentTypes} />
          <FilterSelect label="Career Level" value={careerLevel} onChange={setCareerLevel} options={options.careerLevels} />
        </div>

        {error && (
          <div className="mt-8">
            <EmptyState title="Couldn't load jobs" description={error} />
          </div>
        )}
        {!error && jobs === null && <PageLoader />}
        {!error && jobs !== null && (
          jobs.length ? (
            <div className="mt-8 grid grid-cols-1 gap-4">
              {jobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
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
