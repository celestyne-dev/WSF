// WSF Career Hub — GET /career-hub (normalized Resource + Learning cards,
// paginated) and GET /career-hub/meta (filter vocabulary + New This Month).
// Cards are rendered as-is: the server already decided format, time,
// access level, Circle inclusion and server-formatted prices.
import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { mapMediaRef } from '../utils/media'
import { mapPriceOptions } from './payments'

export function mapCareerHubCard(c) {
  return {
    ...c,
    image: mapMediaRef(c.image),
    pricing: c.pricing ? { ...c.pricing, prices: mapPriceOptions(c.pricing.prices) } : null,
  }
}

export async function fetchCareerHub(params = {}) {
  if (!USE_MOCK) {
    const data = (await apiClient.get('/career-hub', { params })).data
    return { items: data.items.map(mapCareerHubCard), pagination: data.pagination }
  }
  return delay({ items: [], pagination: { page: 1, pageSize: params.pageSize || 12, totalItems: 0, totalPages: 0 } })
}

export async function fetchCareerHubMeta() {
  if (!USE_MOCK) {
    const data = (await apiClient.get('/career-hub/meta')).data
    return { ...data, newThisMonth: (data.newThisMonth || []).map(mapCareerHubCard) }
  }
  return delay({ goals: [], formats: [], access: [], sorts: [], newThisMonth: [] })
}

// --- Private career goals (signed-in user only) ---------------------------

export async function fetchMyCareerGoals() {
  const { data } = await apiClient.get('/career-hub/me/goals')
  return { goals: data?.goals || [], prompted: !!data?.prompted }
}

// goals: Career Hub goal keys (max 3); [] clears them.
export async function saveMyCareerGoals(goals) {
  const { data } = await apiClient.put('/career-hub/me/goals', { goals })
  return { goals: data?.goals || [], prompted: !!data?.prompted }
}

export async function skipCareerGoalsPrompt() {
  const { data } = await apiClient.post('/career-hub/me/goals/skip')
  return { goals: data?.goals || [], prompted: !!data?.prompted }
}

export async function fetchRecommendedForMyGoals() {
  const { data } = await apiClient.get('/career-hub/me/recommended')
  return (data?.items || []).map(mapCareerHubCard)
}
