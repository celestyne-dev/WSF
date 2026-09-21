import { useState, useMemo } from 'react'
import { jobs } from '../mock/jobs'
import { getJobsFilterOptions } from '../api/jobs'
import { matchesCountry, matchesRegion } from '../mock/geography'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import JobCard from '../components/cards/JobCard'
import EmptyState from '../components/ui/EmptyState'

export default function JobsListingPage() {
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
  const [industry, setIndustry] = useState('')
  const [workMode, setWorkMode] = useState('')
  const [careerLevel, setCareerLevel] = useState('')
  const options = useMemo(() => getJobsFilterOptions(), [])

  useSeo({
    title: 'Jobs for Women | Women Shaping Futures',
    description: 'Curated job openings from employers committed to hiring and advancing women, worldwide and remote.',
    canonical: 'https://womenshapingfutures.org/jobs',
  })

  const filtered = jobs.filter(
    (j) =>
      (!country || matchesCountry(j.countryCode, country)) &&
      (!region || matchesRegion(j.countryCode, region)) &&
      (!industry || j.industry === industry) &&
      (!workMode || j.workMode === workMode) &&
      (!careerLevel || j.careerLevel === careerLevel),
  )

  return (
    <div>
      <PageHeader eyebrow="Opportunity" title="Jobs" description="Roles from employers we've vetted for pay transparency and growth potential — worldwide, remote, and hybrid. New listings added weekly." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Country" value={country} onChange={setCountry} options={options.countries} />
          <FilterSelect label="Industry" value={industry} onChange={setIndustry} options={options.industries} />
          <FilterSelect label="Work Mode" value={workMode} onChange={setWorkMode} options={options.workModes} />
          <FilterSelect label="Career Level" value={careerLevel} onChange={setCareerLevel} options={options.careerLevels} />
        </div>

        {filtered.length ? (
          <div className="mt-8 grid grid-cols-1 gap-4">
            {filtered.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        ) : (
          <div className="mt-8">
            <EmptyState title="No jobs match those filters" description="Try clearing a filter, or check back soon — we add new roles every week." />
          </div>
        )}
      </div>
    </div>
  )
}
