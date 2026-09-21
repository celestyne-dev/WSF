import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { COUNTRIES, getCountry } from '../mock/geography'

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

// Attaches a nested { code, name, region } country object to a mock record
// that only carries a flat countryCode — mirroring the shape the real
// backend nests on Person/Author/Organization/Job/Event (CountrySchema).
// Confined to api/* mock branches; presentation components never call
// mock/geography directly, they just read `.country` off the object an
// api/* function already returned.
export function attachMockCountry(item) {
  if (!item) return null
  return { ...item, country: getCountry(item.countryCode) || null }
}

// Builds { value, label } country filter options directly from a list of
// already-normalized items carrying a `.country` object — works
// identically for real-mode items (country nested by the backend) and
// mock-mode items (country attached by attachMockCountry), so it never
// needs its own mock/geography lookup.
export function countryOptionsFromItems(items, getItemCountry = (item) => item.country) {
  const seen = new Map()
  for (const item of items) {
    const country = getItemCountry(item)
    if (country?.code && !seen.has(country.code)) seen.set(country.code, { value: country.code, label: country.name })
  }
  return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label))
}
