import { apiClient, USE_MOCK } from './client'

// POST /api/v1/consent — records the signed-in member's current cookie
// choice (account-linked history; see backend app/api/v1/consent.py).
// Fire-and-forget: the browser's own stored choice already applies.
export async function recordConsent(record) {
  if (USE_MOCK || !record) return null
  const res = await apiClient.post('/consent', {
    consentVersion: record.version,
    preferences: record.preferences,
    analytics: record.analytics,
    marketing: record.marketing,
    decidedAt: record.timestamp,
  })
  return res.data?.data ?? null
}
