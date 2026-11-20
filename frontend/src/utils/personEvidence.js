// Frontend mirror of backend app/services/person_evidence.py — the ONE
// place the Person claim shapes are normalized, so no component has to
// type-check "string or object" itself. Old rows (plain strings, {year,
// title}) and new evidence objects both come out in the same shape.

const s = (v) => (typeof v === 'string' ? v : v == null ? '' : String(v))

export function normalizeAchievement(raw) {
  if (typeof raw === 'string') return { text: raw, date: '', sourceLabel: '', sourceUrl: '' }
  if (!raw || typeof raw !== 'object') return null
  return { text: s(raw.text), date: s(raw.date), sourceLabel: s(raw.sourceLabel), sourceUrl: s(raw.sourceUrl) }
}

export function normalizeAward(raw) {
  if (typeof raw === 'string') return { name: raw, issuer: '', date: '', sourceLabel: '', sourceUrl: '' }
  if (!raw || typeof raw !== 'object') return null
  return { name: s(raw.name), issuer: s(raw.issuer), date: s(raw.date), sourceLabel: s(raw.sourceLabel), sourceUrl: s(raw.sourceUrl) }
}

export function normalizeTimelineItem(raw) {
  if (!raw || typeof raw !== 'object') return null
  return { year: s(raw.year), title: s(raw.title), organization: s(raw.organization), sourceLabel: s(raw.sourceLabel), sourceUrl: s(raw.sourceUrl) }
}

const list = (values, fn) => (Array.isArray(values) ? values.map(fn).filter(Boolean) : [])
export const normalizeAchievements = (v) => list(v, normalizeAchievement)
export const normalizeAwards = (v) => list(v, normalizeAward)
export const normalizeTimeline = (v) => list(v, normalizeTimelineItem)

// "Award Name — Issuer, 2024" (only the parts that exist). Same as the
// server prerender's _award_line.
export function awardLine(award) {
  const detail = [award.issuer, award.date].filter(Boolean).join(', ')
  return detail ? `${award.name} — ${detail}` : award.name
}

export function isPublicHttpUrl(url) {
  return typeof url === 'string' && /^https?:\/\/[^\s/?#]+\.[^\s/?#]+/i.test(url.trim())
}
