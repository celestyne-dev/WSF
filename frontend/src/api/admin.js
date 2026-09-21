import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { ROLE_DEFINITIONS } from '../constants/roles'
import { attachMockCountry } from './geography'

// The mock admin dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockAdmin
async function loadMockAdmin() {
  if (!_mockAdmin) _mockAdmin = await import('../mock/admin')
  return _mockAdmin
}

// GET /api/v1/admin/dashboard — real aggregate counts + trends. No mock
// equivalent needed for the trend arrays beyond the existing static mock
// fixtures (mock mode never had live traffic to aggregate).
export async function fetchAdminDashboard() {
  if (!USE_MOCK) return (await apiClient.get('/admin/dashboard')).data
  const { dashboardStats, pageViewsTrend, topArticlesThisMonth } = await loadMockAdmin()
  return delay({ ...dashboardStats, pageViewsTrend, topArticlesThisMonth })
}

function mapAdminArticle(a) {
  return {
    id: a.id,
    slug: a.slug,
    title: a.title,
    authorName: a.author?.name || null,
    status: a.status,
    date: a.updated_at || a.publish_date,
  }
}

// GET /api/v1/admin/articles — every status, not just published (the
// public article list only ever returns published articles).
export async function fetchAdminArticles(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/articles', { params })
    return { ...data, items: data.items.map(mapAdminArticle) }
  }
  const { adminPipelineArticles } = await loadMockAdmin()
  const rows = [
    ...adminPipelineArticles.map((a) => ({
      id: a.id,
      slug: null,
      title: a.title,
      authorName: null,
      authorSlug: a.authorSlug,
      status: a.status,
      date: a.updatedAt,
    })),
  ]
  let results = rows
  if (params.status) results = results.filter((r) => r.status === params.status)
  if (params.query) results = results.filter((r) => r.title.toLowerCase().includes(params.query.toLowerCase()))
  return delay(paginate(results, params))
}

export async function fetchAdminUsers() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/users', { params: { pageSize: 100 } })
    return data.items.map((u) => ({
      id: u.id,
      name: u.full_name,
      email: u.email,
      roles: (u.roles || []).map((r) => r.name),
      status: u.is_active ? 'active' : 'inactive',
      lastLogin: u.last_login_at,
    }))
  }
  const { adminUsers } = await loadMockAdmin()
  return delay(adminUsers)
}

// The backend only knows role names, not display labels/descriptions —
// merge the real role list with the static ROLE_DEFINITIONS labels so the
// UI shows "Partnerships Manager" instead of "partnerships_manager", while
// which roles actually exist still comes from the backend.
export async function fetchAdminRoles() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/roles')
    return data.map((r) => {
      const known = ROLE_DEFINITIONS.find((d) => d.key === r.name)
      return { key: r.name, label: known?.label || r.name, description: known?.description || null }
    })
  }
  return delay(ROLE_DEFINITIONS)
}

function mapHomepageModuleAdmin(m) {
  return {
    id: m.id,
    type: m.type,
    enabled: m.enabled,
    order: m.sort_order,
    heading: m.heading,
    subheading: m.subheading,
    selectionMode: m.selection_mode,
    config: m.config || {},
  }
}

export async function fetchAdminHomepage() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/homepage')
    return data.map(mapHomepageModuleAdmin)
  }
  const { homepageModules } = await import('../mock/homepageModules')
  return delay([...homepageModules].sort((a, b) => a.order - b.order))
}

export async function saveAdminHomepage(modules) {
  if (!USE_MOCK) {
    const body = {
      modules: modules.map((m) => ({
        type: m.type,
        enabled: m.enabled,
        heading: m.heading,
        subheading: m.subheading,
        selectionMode: m.selectionMode,
        config: m.config || {},
      })),
    }
    const { data } = await apiClient.put('/admin/homepage', body)
    return data.map(mapHomepageModuleAdmin)
  }
  return delay(modules)
}

export async function fetchAdminSettings() {
  if (!USE_MOCK) return (await apiClient.get('/admin/settings')).data
  return delay({})
}

export async function saveAdminSettings(settings) {
  if (!USE_MOCK) return (await apiClient.put('/admin/settings', { settings })).data
  return delay(settings)
}

export async function fetchAnalyticsSummary() {
  if (!USE_MOCK) return (await apiClient.get('/analytics/summary')).data
  return delay([])
}

export async function fetchTrafficSources() {
  if (!USE_MOCK) return (await apiClient.get('/analytics/traffic-sources')).data
  const { trafficBySource } = await loadMockAdmin()
  return delay(trafficBySource)
}

export async function fetchSubscriberGrowth() {
  if (!USE_MOCK) return (await apiClient.get('/analytics/subscriber-growth')).data
  const { subscriberGrowth } = await loadMockAdmin()
  return delay(subscriberGrowth)
}

// Backing data for AdminGenericList's review-queue sections — each hits a
// real, permission-gated admin endpoint built in an earlier phase.
export async function fetchStorySubmissions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/submissions', { params: { pageSize: 100 } })
    return data.items.map((s) => ({
      id: s.id,
      name: s.name,
      countryCode: s.country?.code || null,
      country: s.country ? { code: s.country.code, name: s.country.name, region: s.country.region } : null,
      title: s.title,
      submittedAt: s.submitted_at,
      status: s.status,
    }))
  }
  const { storySubmissions } = await loadMockAdmin()
  return delay(storySubmissions.map(attachMockCountry))
}

export async function fetchNominations() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/nominations', { params: { pageSize: 100 } })
    return data.items.map((n) => ({
      id: n.id,
      nomineeName: n.nominee_name,
      countryCode: n.country?.code || null,
      country: n.country ? { code: n.country.code, name: n.country.name, region: n.country.region } : null,
      category: n.category,
      submittedAt: n.submitted_at,
      status: n.status,
    }))
  }
  const { nominations } = await loadMockAdmin()
  return delay(nominations.map(attachMockCountry))
}

export async function fetchPartnershipInquiries() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/partnerships/inquiries', { params: { pageSize: 100 } })
    return data.items.map((p) => ({
      id: p.id,
      company: p.company,
      interest: p.interest,
      submittedAt: p.submitted_at,
      status: p.status,
    }))
  }
  const { partnershipInquiries } = await loadMockAdmin()
  return delay(partnershipInquiries)
}

// Ad campaigns have no backend model yet — nothing in Phase 5-7 built ad
// serving/tracking. Real mode returns an empty list rather than silently
// substituting mock data; AdminGenericList shows an explicit "not yet
// available" message for this section.
export async function fetchAdCampaigns() {
  if (!USE_MOCK) return []
  const { adCampaigns } = await loadMockAdmin()
  return delay(adCampaigns)
}

export async function fetchRedirects() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/redirects', { params: { pageSize: 50 } })
    return data.items.map((r) => ({ from: r.fromSlug, to: r.toSlug }))
  }
  return delay([{ from: '/articles/how-women-are-redefining-leadership', to: '/how-women-are-redefining-leadership' }])
}
