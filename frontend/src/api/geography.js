import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { COUNTRIES } from '../mock/geography'

// GET /api/v1/public/countries — the Country reference table. The 8-region
// taxonomy (REGIONS) and GLOBAL/REMOTE pseudo-locations are a fixed
// taxonomy, not CMS data, and stay in mock/geography.js; the country list
// itself is the thing an admin can add to over time, so it comes from the
// backend in real mode.
export async function fetchCountries() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/public/countries')
    return data
  }
  return delay(COUNTRIES)
}
