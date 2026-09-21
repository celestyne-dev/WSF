import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'
import { attachMockCountry, countryOptionsFromItems } from './geography'

// The mock jobs dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockJobs
async function loadMockJobs() {
  if (!_mockJobs) _mockJobs = await import('../mock/jobs')
  return _mockJobs
}

function mapJob(j) {
  if (!j) return null
  return {
    id: j.id,
    slug: j.slug,
    title: j.title,
    company: j.company_name,
    companySlug: j.organization?.slug || null,
    logo: j.logo?.public_url || null,
    location: j.location,
    countryCode: j.country?.code || j.country_code || null,
    country: j.country ? { code: j.country.code, name: j.country.name, region: j.country.region } : null,
    workMode: j.work_mode,
    employmentType: j.employment_type,
    careerLevel: j.career_level,
    industry: j.industry,
    salaryMin: j.salary_min,
    salaryMax: j.salary_max,
    currency: j.currency,
    salaryPeriod: j.salary_period,
    description: j.description,
    responsibilities: j.responsibilities || [],
    requirements: j.requirements || [],
    benefits: j.benefits || [],
    applicationUrl: j.application_url,
    applicationInstructions: j.application_instructions,
    deadline: j.deadline,
    featured: j.featured,
    sponsored: j.sponsored,
    publishedDate: j.published_date,
    expiryDate: j.expiry_date,
  }
}

export async function fetchJobs(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/jobs', { params })
    return { ...data, items: data.items.map(mapJob) }
  }
  const { jobs } = await loadMockJobs()
  let results = [...jobs]
  if (params.country) results = results.filter((j) => matchesCountry(j.countryCode, params.country))
  if (params.region) results = results.filter((j) => matchesRegion(j.countryCode, params.region))
  if (params.industry) results = results.filter((j) => j.industry === params.industry)
  if (params.workMode) results = results.filter((j) => j.workMode === params.workMode)
  if (params.careerLevel) results = results.filter((j) => j.careerLevel === params.careerLevel)
  if (params.employmentType) results = results.filter((j) => j.employmentType === params.employmentType)
  if (params.organization) results = results.filter((j) => j.companySlug === params.organization)
  if (params.featured) results = results.filter((j) => j.featured)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((j) => j.title.toLowerCase().includes(q) || j.company.toLowerCase().includes(q))
  }
  results.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0))
  const page = paginate(results, params)
  return delay({ ...page, items: page.items.map(attachMockCountry) })
}

export async function fetchJobBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/jobs/${slug}`)
      return mapJob(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getJobBySlug } = await loadMockJobs()
  return delay(attachMockCountry(getJobBySlug(slug)))
}

export async function fetchJobsFilterOptions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/jobs', { params: { pageSize: 100 } })
    const all = data.items.map(mapJob)
    return {
      countries: countryOptionsFromItems(all),
      regions: regionFilterOptions(),
      industries: [...new Set(all.map((j) => j.industry))].filter(Boolean).sort(),
      workModes: [...new Set(all.map((j) => j.workMode))].filter(Boolean).sort(),
      careerLevels: [...new Set(all.map((j) => j.careerLevel))].filter(Boolean),
      employmentTypes: [...new Set(all.map((j) => j.employmentType))].filter(Boolean),
    }
  }
  const { jobs } = await loadMockJobs()
  const enriched = jobs.map(attachMockCountry)
  return delay({
    countries: countryOptionsFromItems(enriched),
    regions: regionFilterOptions(),
    industries: [...new Set(jobs.map((j) => j.industry))].sort(),
    workModes: [...new Set(jobs.map((j) => j.workMode))].sort(),
    careerLevels: [...new Set(jobs.map((j) => j.careerLevel))],
    employmentTypes: [...new Set(jobs.map((j) => j.employmentType))],
  })
}
