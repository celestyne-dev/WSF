import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'

// Mock analytics fixtures are only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches them.
let _mockAnalytics
async function loadMockAnalytics() {
  if (!_mockAnalytics) _mockAnalytics = await import('../mock/analyticsDashboard')
  return _mockAnalytics
}

function rangeParams({ start, end, compare } = {}) {
  const params = {}
  if (start) params.start = start
  if (end) params.end = end
  if (compare) params.compare = true
  return params
}

// GET /api/v1/analytics/overview — headline KPIs, trend, audience-by-source.
export async function fetchAnalyticsOverview(range) {
  if (!USE_MOCK) return (await apiClient.get('/analytics/overview', { params: rangeParams(range) })).data
  const { overview } = await loadMockAnalytics()
  return delay(overview)
}

export async function fetchAnalyticsContent(range, { sort = 'views', page = 1, perPage = 20 } = {}) {
  if (!USE_MOCK) return (await apiClient.get('/analytics/content', { params: { ...rangeParams(range), sort, page, perPage } })).data
  const { content } = await loadMockAnalytics()
  return delay(content)
}

export async function fetchAnalyticsSearch(range) {
  if (!USE_MOCK) return (await apiClient.get('/analytics/search-report', { params: rangeParams(range) })).data
  const { search } = await loadMockAnalytics()
  return delay(search)
}

export async function fetchAnalyticsNewsletter(range) {
  if (!USE_MOCK) return (await apiClient.get('/analytics/newsletter', { params: rangeParams(range) })).data
  const { newsletter } = await loadMockAnalytics()
  return delay(newsletter)
}

export async function fetchAnalyticsCareers(range) {
  if (!USE_MOCK) return (await apiClient.get('/analytics/careers', { params: rangeParams(range) })).data
  const { careers } = await loadMockAnalytics()
  return delay(careers)
}

export async function fetchAnalyticsCommunityPrograms(range) {
  if (!USE_MOCK) return (await apiClient.get('/analytics/community-programs', { params: rangeParams(range) })).data
  const { communityPrograms } = await loadMockAnalytics()
  return delay(communityPrograms)
}

// Commercial analytics requires analytics.commercial — a 403 here means
// "not authorized for this section", not an error to surface generically;
// callers check for it explicitly.
export async function fetchAnalyticsCommercial(range) {
  if (!USE_MOCK) return (await apiClient.get('/analytics/commercial', { params: rangeParams(range) })).data
  const { commercial } = await loadMockAnalytics()
  return delay(commercial)
}

// CSV exports need the same Authorization header as any other admin
// request, so a plain <a href> or window.open() to the raw URL won't
// work (there's no auth cookie, only the JWT this axios instance
// attaches per-request) — fetch as a blob through apiClient instead and
// trigger the browser's normal save flow from that. Real mode only;
// there is nothing meaningful to export from static mock fixtures.
async function downloadCsv(path, range) {
  const response = await apiClient.get(path, { params: rangeParams(range), responseType: 'blob' })
  const disposition = response.headers['content-disposition'] || ''
  const match = disposition.match(/filename=([^;]+)/)
  const filename = match ? match[1].trim() : 'export.csv'
  const url = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export function exportAnalyticsContent(range) {
  return downloadCsv('/analytics/export/content', range)
}
export function exportAnalyticsSearch(range) {
  return downloadCsv('/analytics/export/search', range)
}
export function exportAnalyticsSponsors(range) {
  return downloadCsv('/analytics/export/sponsors', range)
}
