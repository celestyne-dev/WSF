import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import {
  adminPipelineArticles,
  adminUsers,
  roleDefinitions,
  storySubmissions,
  nominations,
  partnershipInquiries,
  adCampaigns,
  dashboardStats,
  pageViewsTrend,
  trafficBySource,
  topArticlesThisMonth,
  subscriberGrowth,
} from '../mock/admin'

// GET /api/v1/admin/dashboard — real aggregate counts + trends. No mock
// equivalent needed for the trend arrays beyond the existing static mock
// fixtures (mock mode never had live traffic to aggregate).
export async function fetchAdminDashboard() {
  if (!USE_MOCK) return (await apiClient.get('/admin/dashboard')).data
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
  return delay(adminUsers)
}

export async function fetchAdminRoles() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/roles')
    return data.map((r) => ({ key: r.name, label: r.name, description: r.description }))
  }
  return delay(roleDefinitions)
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
  return delay(trafficBySource)
}

export async function fetchSubscriberGrowth() {
  if (!USE_MOCK) return (await apiClient.get('/analytics/subscriber-growth')).data
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
      title: s.title,
      submittedAt: s.submitted_at,
      status: s.status,
    }))
  }
  return delay(storySubmissions)
}

export async function fetchNominations() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/nominations', { params: { pageSize: 100 } })
    return data.items.map((n) => ({
      id: n.id,
      nomineeName: n.nominee_name,
      countryCode: n.country?.code || null,
      category: n.category,
      submittedAt: n.submitted_at,
      status: n.status,
    }))
  }
  return delay(nominations)
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
  return delay(partnershipInquiries)
}

// Ad campaigns have no backend model yet — nothing in Phase 5-7 built ad
// serving/tracking. Real mode returns an empty list rather than silently
// substituting mock data; AdminGenericList shows an explicit "not yet
// available" message for this section.
export async function fetchAdCampaigns() {
  if (!USE_MOCK) return []
  return delay(adCampaigns)
}

export async function fetchMediaLibrary() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/media', { params: { pageSize: 24 } })
    return data.items.map((m) => ({ id: m.id, mediaPath: m.public_url, alt: m.alt_text, caption: m.caption }))
  }
  const { articles } = await import('../mock/articles')
  return delay(
    articles.slice(0, 6).map((a) => ({ id: a.heroImage, mediaPath: a.heroImage, alt: a.heroImageAlt, caption: a.heroImageCaption })),
  )
}

export async function fetchRedirects() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/redirects', { params: { pageSize: 50 } })
    return data.items.map((r) => ({ from: r.fromSlug, to: r.toSlug }))
  }
  return delay([{ from: '/articles/how-women-are-redefining-leadership', to: '/how-women-are-redefining-leadership' }])
}
