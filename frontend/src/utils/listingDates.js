// Date wording for Jobs and Opportunities (cards, detail pages, Studio),
// one place so components never compute it differently. Dates are
// calendar dates ("2026-11-30"): formatted from their Y/M/D parts in UTC so
// no viewer timezone can shift them by a day. "Days left" and "closing
// soon" come from the server (listing_lifecycle.closing_info) rather than
// the viewer's clock.

const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function parts(iso) {
  const m = typeof iso === 'string' ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null
  if (!m) return null
  return { y: Number(m[1]), mo: Number(m[2]) - 1, d: Number(m[3]) }
}

/** "18 November 2026" */
export function longDate(iso) {
  const p = parts(iso)
  return p ? `${p.d} ${MONTHS_LONG[p.mo]} ${p.y}` : ''
}

/** "18 Nov" (adds the year when it is not `currentYear`). */
export function shortDate(iso, currentYear = new Date().getUTCFullYear()) {
  const p = parts(iso)
  if (!p) return ''
  return p.y === currentYear ? `${p.d} ${MONTHS_SHORT[p.mo]}` : `${p.d} ${MONTHS_SHORT[p.mo]} ${p.y}`
}

/** Card/detail closing line from the server's `closing` object:
 *  "Closes today" / "Closes tomorrow" / "Closes 30 Nov · 9 days left". */
export function closingLabel(closing, currentYear) {
  if (!closing || typeof closing.daysLeft !== 'number') return ''
  if (closing.daysLeft <= 0) return 'Closes today'
  if (closing.daysLeft === 1) return 'Closes tomorrow'
  return `Closes ${shortDate(closing.closesOn, currentYear)} · ${closing.daysLeft} days left`
}

export function isClosingSoon(closing) {
  return Boolean(closing?.closingSoon)
}

export const postedLabel = (iso, currentYear) => (iso ? `Posted ${shortDate(iso, currentYear)}` : '')
export const opensLabel = (iso) => (iso ? `Opens ${longDate(iso)}` : '')

/** Studio label for the server's effective_state. */
export const EFFECTIVE_STATE_LABELS = {
  draft: 'Draft',
  review: 'In review',
  scheduled: 'Scheduled',
  open: 'Open',
  closing_soon: 'Closing soon',
  deadline_passed: 'Deadline passed',
  upcoming: 'Upcoming',
  expired: 'Expired',
  closed: 'Closed',
  archived: 'Archived',
}
