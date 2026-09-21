// Global geography reference data. This is the single source of truth for
// country/region metadata across the platform — no feature should maintain
// its own hard-coded country list. In production this mirrors a `Country`
// reference table (ISO 3166-1 alpha-2 codes) that Person, Author, Job,
// Opportunity, Event, Organization, StorySubmission, and Nomination all
// foreign-key into, rather than storing free-text country names.
//
// Adding support for a new country is a one-line addition here — nothing
// else in the app needs to change.

export const REGIONS = [
  'North America',
  'Latin America & Caribbean',
  'Europe',
  'Africa',
  'Asia',
  'Middle East',
  'Oceania',
  'Global',
]

// A representative (not exhaustive) set of ISO 3166-1 alpha-2 countries
// spanning every region — enough to demonstrate genuinely global coverage.
// Extending this list to the full ISO-3166 set is a data change only.
export const COUNTRIES = [
  // North America
  { code: 'US', name: 'United States', region: 'North America' },
  { code: 'CA', name: 'Canada', region: 'North America' },

  // Latin America & Caribbean
  { code: 'BR', name: 'Brazil', region: 'Latin America & Caribbean' },
  { code: 'MX', name: 'Mexico', region: 'Latin America & Caribbean' },
  { code: 'CO', name: 'Colombia', region: 'Latin America & Caribbean' },
  { code: 'AR', name: 'Argentina', region: 'Latin America & Caribbean' },

  // Europe
  { code: 'GB', name: 'United Kingdom', region: 'Europe' },
  { code: 'DE', name: 'Germany', region: 'Europe' },
  { code: 'FR', name: 'France', region: 'Europe' },
  { code: 'IE', name: 'Ireland', region: 'Europe' },
  { code: 'NL', name: 'Netherlands', region: 'Europe' },
  { code: 'ES', name: 'Spain', region: 'Europe' },
  { code: 'SE', name: 'Sweden', region: 'Europe' },
  { code: 'PT', name: 'Portugal', region: 'Europe' },

  // Africa
  { code: 'KE', name: 'Kenya', region: 'Africa' },
  { code: 'NG', name: 'Nigeria', region: 'Africa' },
  { code: 'ZA', name: 'South Africa', region: 'Africa' },
  { code: 'GH', name: 'Ghana', region: 'Africa' },
  { code: 'EG', name: 'Egypt', region: 'Africa' },
  { code: 'RW', name: 'Rwanda', region: 'Africa' },
  { code: 'ET', name: 'Ethiopia', region: 'Africa' },
  { code: 'TZ', name: 'Tanzania', region: 'Africa' },
  { code: 'UG', name: 'Uganda', region: 'Africa' },
  { code: 'SN', name: 'Senegal', region: 'Africa' },

  // Asia
  { code: 'IN', name: 'India', region: 'Asia' },
  { code: 'SG', name: 'Singapore', region: 'Asia' },
  { code: 'PH', name: 'Philippines', region: 'Asia' },
  { code: 'JP', name: 'Japan', region: 'Asia' },
  { code: 'ID', name: 'Indonesia', region: 'Asia' },
  { code: 'VN', name: 'Vietnam', region: 'Asia' },
  { code: 'KR', name: 'South Korea', region: 'Asia' },

  // Middle East
  { code: 'AE', name: 'United Arab Emirates', region: 'Middle East' },
  { code: 'SA', name: 'Saudi Arabia', region: 'Middle East' },
  { code: 'IL', name: 'Israel', region: 'Middle East' },
  { code: 'JO', name: 'Jordan', region: 'Middle East' },

  // Oceania
  { code: 'AU', name: 'Australia', region: 'Oceania' },
  { code: 'NZ', name: 'New Zealand', region: 'Oceania' },
]

// Pseudo-locations used where a specific country doesn't apply.
export const GLOBAL = { code: 'GLOBAL', name: 'Global', region: 'Global' }
export const REMOTE = { code: 'REMOTE', name: 'Remote', region: 'Global' }

const COUNTRY_MAP = new Map(COUNTRIES.map((c) => [c.code, c]))

export function getCountry(code) {
  if (code === GLOBAL.code) return GLOBAL
  if (code === REMOTE.code) return REMOTE
  return COUNTRY_MAP.get(code) || null
}

export function getCountryName(code) {
  return getCountry(code)?.name || code
}

export function getRegionForCountry(code) {
  return getCountry(code)?.region || null
}

export function getCountryNames(codes = []) {
  return codes.map(getCountryName)
}

export const ALL_COUNTRY_CODES = COUNTRIES.map((c) => c.code)

// Builds { value, label } options for a country <select> from whatever
// country codes actually appear in a dataset (a listing shouldn't offer a
// country with zero results) — sorted by display name. Pass a flat list of
// codes, e.g. `items.map((i) => i.countryCode)`, or `items.flatMap(...)`
// for fields like `countriesEligible` that hold an array per item.
export function countryFilterOptions(codes = []) {
  const unique = [...new Set(codes.filter(Boolean))]
  return unique
    .map((code) => ({ value: code, label: getCountryName(code) }))
    .sort((a, b) => a.label.localeCompare(b.label))
}

export function regionFilterOptions() {
  return REGIONS.map((r) => ({ value: r, label: r }))
}

// True if `code` (a single country code, or an array of them for
// multi-country eligibility) falls within `region`.
export function matchesRegion(code, region) {
  const codes = Array.isArray(code) ? code : [code]
  return codes.some((c) => getRegionForCountry(c) === region)
}

export function matchesCountry(code, targetCode) {
  const codes = Array.isArray(code) ? code : [code]
  return codes.includes(targetCode)
}
