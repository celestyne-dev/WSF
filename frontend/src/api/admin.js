import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { ROLE_DEFINITIONS } from '../constants/roles'
import { mapMediaRef } from '../utils/media'

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

// Internal CMS staff directory only — never Community Members, public
// People/Authors, Newsletter subscribers, or Mentorship/Submission/
// Nomination applicants (see backend app/services/user_admin.py's own
// docstring for the same boundary). `is_active`/`role`/`q` map straight
// through to GET /admin/users' query filters; `page`/`pageSize` through
// the shared pagination convention (see api/client.js's param translator).
function mapAdminUser(u) {
  return {
    id: u.id,
    firstName: u.first_name,
    lastName: u.last_name,
    name: u.full_name,
    email: u.email,
    roles: (u.roles || []).map((r) => r.name),
    isActive: u.is_active,
    lastLogin: u.last_login_at,
    createdAt: u.created_at,
    updatedAt: u.updated_at,
  }
}

export async function fetchAdminUsers(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/users', {
      params: { q: params.query, role: params.role, isActive: params.isActive, page: params.page, pageSize: params.pageSize || 20 },
    })
    return { items: data.items.map(mapAdminUser), pagination: data.pagination }
  }
  const { adminUsers } = await loadMockAdmin()
  let rows = adminUsers.map((u) => ({
    id: u.id,
    firstName: u.name.split(' ')[0],
    lastName: u.name.split(' ').slice(1).join(' '),
    name: u.name,
    email: u.email,
    roles: u.roles || [u.role],
    isActive: u.status !== 'inactive',
    lastLogin: u.lastLogin,
    createdAt: u.lastLogin,
    updatedAt: u.lastLogin,
  }))
  if (params.query) {
    const q = params.query.toLowerCase()
    rows = rows.filter((u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))
  }
  if (params.role) rows = rows.filter((u) => u.roles.includes(params.role))
  if (params.isActive !== undefined && params.isActive !== '') {
    const wantActive = params.isActive === true || params.isActive === 'true'
    rows = rows.filter((u) => u.isActive === wantActive)
  }
  return delay(paginate(rows, params))
}

// Mock mode has no mutable staff-account store (see community.js's own
// write functions for the same established limitation) — creation, edits,
// activation/deactivation, role assignment, and password resets always
// call the real backend even under VITE_USE_MOCK=true. The manual
// verification for this module is run with VITE_USE_MOCK=false for
// exactly this reason.
export async function fetchAdminUser(id) {
  const { data } = await apiClient.get(`/admin/users/${id}`)
  return mapAdminUser(data)
}

export async function createAdminUser({ email, firstName, lastName, roleNames, isActive }) {
  const { data } = await apiClient.post('/admin/users', {
    email,
    first_name: firstName,
    last_name: lastName,
    role_names: roleNames,
    is_active: isActive,
  })
  return { user: mapAdminUser(data), temporaryPassword: data.temporary_password }
}

export async function updateAdminUser(id, { firstName, lastName, email, countryCode }) {
  const { data } = await apiClient.patch(`/admin/users/${id}`, {
    first_name: firstName,
    last_name: lastName,
    email,
    country_code: countryCode,
  })
  return mapAdminUser(data)
}

export async function setAdminUserStatus(id, isActive) {
  const { data } = await apiClient.patch(`/admin/users/${id}/status`, { is_active: isActive })
  return mapAdminUser(data)
}

export async function assignAdminUserRoles(id, roleNames) {
  const { data } = await apiClient.put(`/admin/users/${id}/roles`, { role_names: roleNames })
  return mapAdminUser(data)
}

export async function resetAdminUserPassword(id) {
  const { data } = await apiClient.post(`/admin/users/${id}/reset-password`)
  return data.temporary_password
}

// The backend only knows role names, not display labels/descriptions —
// merge the real role list with the static ROLE_DEFINITIONS labels so the
// UI shows "Partnerships Manager" instead of "partnerships_manager", while
// which roles/permissions actually exist, and how many users hold each
// one, still comes from the backend.
function mapAdminRole(r) {
  const known = ROLE_DEFINITIONS.find((d) => d.key === r.name)
  return {
    id: r.id,
    key: r.name,
    label: known?.label || r.name,
    description: known?.description || r.description || null,
    userCount: r.user_count ?? 0,
    permissions: (r.permissions || []).map((p) => p.name),
  }
}

export async function fetchAdminRoles() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/roles')
    return data.map(mapAdminRole)
  }
  return delay(ROLE_DEFINITIONS.map((r) => ({ ...r, id: r.key, userCount: 0, permissions: [] })))
}

// `id` is the numeric Role.id GET /admin/roles/<id> expects — not the
// role name/key (see mapAdminRole).
export async function fetchAdminRole(id) {
  const { data } = await apiClient.get(`/admin/roles/${id}`)
  return mapAdminRole(data)
}

// Read-only reference list for the Roles/Permission-matrix screen —
// permissions themselves are code-defined (see backend
// app/services/rbac.py), never admin-creatable.
export async function fetchAdminPermissions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/permissions')
    return data.map((p) => ({ name: p.name, description: p.description }))
  }
  return delay([])
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
    mediaId: m.media_id,
    media: mapMediaRef(m.media),
    ctaLabel: m.cta_label,
    ctaUrl: m.cta_url,
    secondaryCtaLabel: m.secondary_cta_label,
    secondaryCtaUrl: m.secondary_cta_url,
    updatedAt: m.updated_at,
    warnings: m.warnings || [],
  }
}

export async function fetchAdminHomepage() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/homepage')
    return data.map(mapHomepageModuleAdmin)
  }
  const { homepageModules } = await import('../mock/homepageModules')
  return delay([...homepageModules].sort((a, b) => a.order - b.order).map((m) => ({ ...m, warnings: [] })))
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
        mediaId: m.mediaId ?? null,
        ctaLabel: m.ctaLabel ?? null,
        ctaUrl: m.ctaUrl ?? null,
        secondaryCtaLabel: m.secondaryCtaLabel ?? null,
        secondaryCtaUrl: m.secondaryCtaUrl ?? null,
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

export async function fetchRedirects() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/redirects', { params: { pageSize: 50 } })
    return data.items.map((r) => ({ from: r.fromSlug, to: r.toSlug }))
  }
  return delay([{ from: '/articles/how-women-are-redefining-leadership', to: '/how-women-are-redefining-leadership' }])
}

// GET /api/v1/admin/sponsors — active sponsorship deals, for the Job
// editor's sponsor selector. Read-only; full Sponsor CRUD is a separate
// future CMS module.
export async function fetchSponsors() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/sponsors')
    return data.map((s) => ({ id: s.id, tier: s.tier, organizationName: s.organization?.name || null }))
  }
  return delay([])
}
