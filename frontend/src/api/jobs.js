import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'
import { attachMockCountry, countryOptionsFromItems } from './geography'
import { mapMediaRef } from '../utils/media'

// The mock jobs dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockJobs
async function loadMockJobs() {
  if (!_mockJobs) _mockJobs = await import('../mock/jobs')
  return _mockJobs
}

function asList(value) {
  return Array.isArray(value) ? value : []
}

function mapJob(j) {
  if (!j) return null
  return {
    id: j.id,
    slug: j.slug,
    title: j.title,
    company: j.company_name,
    companySlug: j.organization?.slug || null,
    organizationId: j.organization_id || j.organization?.id || null,
    logo: j.organization?.logo?.public_url || j.logo?.public_url || null,
    logoMedia: mapMediaRef(j.organization?.logo || j.logo),
    logoMediaId: j.logo?.id || null,
    location: j.location,
    city: j.city,
    countryCode: j.country?.code || j.country_code || null,
    country: j.country ? { code: j.country.code, name: j.country.name, region: j.country.region } : null,
    workMode: j.work_mode,
    remoteScope: j.remote_scope,
    remoteRegion: j.remote_region,
    employmentType: j.employment_type,
    careerLevel: j.career_level,
    industry: j.industry,
    salaryMin: j.salary_min,
    salaryMax: j.salary_max,
    currency: j.currency,
    salaryPeriod: j.salary_period,
    salaryVisible: j.salary_visible ?? true,
    shortDescription: j.short_description,
    // Ordered content-block list — same shape as Article.content, rendered
    // with the shared ArticleContent component and edited with the shared
    // ArticleBlockEditor. Mock-mode demo data still carries a plain
    // string, wrapped into a single paragraph block so both modes share
    // one shape.
    description: Array.isArray(j.description) ? j.description : j.description ? [{ type: 'paragraph', text: j.description }] : [],
    responsibilities: asList(j.responsibilities),
    requirements: asList(j.requirements),
    qualifications: asList(j.qualifications),
    skills: asList(j.skills),
    benefits: asList(j.benefits),
    applicationUrl: j.application_url,
    applicationEmail: j.application_email,
    applicationInstructions: j.application_instructions,
    deadline: j.deadline,
    featured: j.featured,
    sponsored: j.sponsored,
    sponsorId: j.sponsor_id || j.sponsor?.id || null,
    sponsorTier: j.sponsor?.tier || null,
    status: j.status || 'published',
    isClosed: j.is_closed ?? false,
    isScheduled: j.is_scheduled ?? false,
    seo: j.seo || null,
    publishedDate: j.published_date,
    expiryDate: j.expiry_date,
  }
}

// Mock demo jobs still carry a plain-string `description` (pre-dating the
// block-content shape the real API now returns) — wrapped into a single
// paragraph block so both modes share one shape.
function normalizeMockJobDescription(item) {
  if (!item) return item
  return {
    ...item,
    description: Array.isArray(item.description) ? item.description : item.description ? [{ type: 'paragraph', text: item.description }] : [],
    responsibilities: asList(item.responsibilities),
    requirements: asList(item.requirements),
    qualifications: asList(item.qualifications),
    skills: asList(item.skills),
    benefits: asList(item.benefits),
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
  if (params.city) results = results.filter((j) => (j.city || '').toLowerCase() === params.city.toLowerCase())
  if (params.industry) results = results.filter((j) => j.industry === params.industry)
  if (params.workMode) results = results.filter((j) => j.workMode === params.workMode)
  if (params.careerLevel) results = results.filter((j) => j.careerLevel === params.careerLevel)
  if (params.employmentType) results = results.filter((j) => j.employmentType === params.employmentType)
  if (params.organization) results = results.filter((j) => j.companySlug === params.organization)
  if (params.featured) results = results.filter((j) => j.featured)
  if (params.salaryMin) results = results.filter((j) => !j.salaryMax || j.salaryMax >= Number(params.salaryMin))
  if (params.salaryMax) results = results.filter((j) => !j.salaryMin || j.salaryMin <= Number(params.salaryMax))
  if (params.closingWithinDays) {
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() + Number(params.closingWithinDays))
    results = results.filter((j) => j.deadline && new Date(j.deadline) <= cutoff)
  }
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((j) => j.title.toLowerCase().includes(q) || j.company.toLowerCase().includes(q))
  }
  if (params.sort === 'deadline') {
    results.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0) || new Date(a.deadline || 0) - new Date(b.deadline || 0))
  } else {
    results.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0))
  }
  const page = paginate(results, params)
  return delay({ ...page, items: page.items.map(attachMockCountry).map(normalizeMockJobDescription) })
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
  return delay(normalizeMockJobDescription(attachMockCountry(getJobBySlug(slug))))
}

// POST/PUT /api/v1/jobs — CMS create/update. Field names mirror
// JobInputSchema's camelCase data_keys exactly.
export async function createJob(payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/jobs', payload)
    return mapJob(data)
  }
  return delay({ ...payload, id: `mock-${Date.now()}`, slug: payload.slug })
}

export async function updateJob(slug, payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.put(`/jobs/${slug}`, payload)
    return mapJob(data)
  }
  return delay({ ...payload, slug: payload.slug || slug })
}

export async function deleteJob(slug) {
  if (!USE_MOCK) {
    await apiClient.delete(`/jobs/${slug}`)
    return
  }
  return delay(undefined)
}

export async function duplicateJob(slug) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post(`/jobs/${slug}/duplicate`)
    return mapJob(data)
  }
  return delay({ id: `mock-${Date.now()}`, slug: `${slug}-copy` })
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
      companies: [...new Set(all.map((j) => j.companySlug ? j.company : null))].filter(Boolean).sort().map((name) => {
        const job = all.find((j) => j.company === name)
        return { value: job?.companySlug, label: name }
      }).filter((o) => o.value),
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
    companies: [...new Set(jobs.map((j) => j.companySlug))].filter(Boolean).map((slug) => {
      const job = jobs.find((j) => j.companySlug === slug)
      return { value: slug, label: job?.company }
    }),
  })
}
