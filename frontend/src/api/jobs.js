import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { jobs, getJobBySlug as findBySlug } from '../mock/jobs'
import { countryFilterOptions, regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'

export async function fetchJobs(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/jobs', { params })
    return data
  }
  let results = [...jobs]
  if (params.country) results = results.filter((j) => matchesCountry(j.countryCode, params.country))
  if (params.region) results = results.filter((j) => matchesRegion(j.countryCode, params.region))
  if (params.industry) results = results.filter((j) => j.industry === params.industry)
  if (params.workMode) results = results.filter((j) => j.workMode === params.workMode)
  if (params.careerLevel) results = results.filter((j) => j.careerLevel === params.careerLevel)
  if (params.employmentType) results = results.filter((j) => j.employmentType === params.employmentType)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((j) => j.title.toLowerCase().includes(q) || j.company.toLowerCase().includes(q))
  }
  results.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0))
  return delay(paginate(results, params))
}

export async function fetchJobBySlug(slug) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/jobs/${slug}`)
    return data
  }
  return delay(findBySlug(slug) || null)
}

export function getJobsFilterOptions() {
  return {
    countries: countryFilterOptions(jobs.map((j) => j.countryCode)),
    regions: regionFilterOptions(),
    industries: [...new Set(jobs.map((j) => j.industry))].sort(),
    workModes: [...new Set(jobs.map((j) => j.workMode))].sort(),
    careerLevels: [...new Set(jobs.map((j) => j.careerLevel))],
    employmentTypes: [...new Set(jobs.map((j) => j.employmentType))],
  }
}
