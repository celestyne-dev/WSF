// WSF Circle plan + membership display rules (pure, Node-testable), shared
// by CirclePage, AccountMembershipPage and the admin membership screens so
// Monthly / Yearly / Lifetime are always worded the same way. Display
// only — entitlement always comes from the server (hasAccess /
// yearlyLevelAccess from GET /circle/me).

export const INTERVAL_LABEL = { monthly: 'Monthly', yearly: 'Yearly', lifetime: 'Lifetime' }

export function intervalLabel(interval) {
  return INTERVAL_LABEL[interval] || INTERVAL_LABEL.monthly
}

// Price suffix next to a plan price.
export function planPriceSuffix(plan) {
  if (plan?.billingInterval === 'lifetime') return 'one-time'
  return plan?.billingInterval === 'yearly' ? '/ year' : '/ month'
}

export function planTagline(plan) {
  if (plan?.billingInterval === 'lifetime') return 'Pay once. Keep growing with WSF for life.'
  return plan?.billingInterval === 'yearly' ? 'Best for ongoing career growth' : 'Flexible access'
}

// The three short facts shown on a Lifetime plan card.
export const LIFETIME_PLAN_HIGHLIGHTS = ['One-time payment', 'No renewal', 'Lifetime access to eligible WSF digital membership benefits']

// Founding / capacity presentation from the server's real availability.
// Never invents scarcity: "X places remaining" only when the backend sends
// a remaining count for a limited plan.
export function planOfferState(plan) {
  const availability = plan?.availability || {}
  const heading = plan?.isFounding ? 'Founding Lifetime Membership' : null
  if (!availability.limited) return { heading, status: null, remaining: null, full: false }
  if (availability.full) {
    return { heading, status: plan?.isFounding ? 'Founding offer full' : 'Plan full', remaining: 0, full: true }
  }
  const remaining = Number.isInteger(availability.remaining) ? availability.remaining : null
  return {
    heading,
    status: 'Limited availability',
    remaining,
    remainingText: remaining !== null ? `${remaining} ${remaining === 1 ? 'place' : 'places'} remaining` : null,
    full: false,
  }
}

// One sentence per interval actually offered — never mentions a plan type
// that isn't configured. Mirrors spa_shell.py's _circle_plan_guidance().
export function planGuidance(plans) {
  const intervals = new Set((plans || []).map((p) => p.billingInterval))
  const parts = []
  if (intervals.has('monthly')) parts.push('Choose Monthly for flexibility.')
  if (intervals.has('yearly')) parts.push('Choose Yearly for ongoing career growth and exclusive annual-member bonuses.')
  if (intervals.has('lifetime')) {
    parts.push('Choose Lifetime to pay once and keep growing with WSF for life — lifetime access to eligible WSF Circle digital membership benefits, with no renewal.')
  }
  return parts.join(' ')
}

// Benefits heading for plans whose members get the annual-member bonuses.
export function planExtrasHeading(plan) {
  if (plan?.billingInterval === 'lifetime') return 'Lifetime member benefits'
  if (plan?.billingInterval === 'yearly') return 'Yearly member extras'
  return null
}

export const LIFETIME_SCOPE_NOTE = 'Lifetime access to eligible WSF Circle digital membership benefits.'

// Shown once on the Circle page (not on every card): what Lifetime covers
// and what stays separately sold.
export const LIFETIME_INCLUDED = [
  'All WSF digital Resources, including Premium, Circle-only and yearly bonus Resources',
  'All WSF Learning courses, programmes and challenges — including ones normally sold individually',
  'Future eligible WSF digital Resources and courses, and updates to the ones you have',
  'Full Career Hub access and every yearly-level Circle benefit',
]
export const LIFETIME_EXCLUSIONS =
  'Separately sold services stay outside membership unless stated otherwise — for example 1:1 coaching or consulting, cohort programmes with live delivery costs, ticketed conferences and events, partner or third-party programmes, and physical products.'

// "Lifetime Member" / "Founding Lifetime Member" (server-computed) or null.
export function memberBadge(subscription) {
  return subscription?.memberBadge || null
}

function isLifetime(subscription) {
  return !!(subscription?.isLifetime || subscription?.plan?.billingInterval === 'lifetime')
}

// The renewal/expiry lines for a membership. Lifetime never shows a renewal
// or expiry date — it reads "Lifetime access · No renewal required" while
// active; once staff end it (revoked/cancelled/expired) the ended date is
// what's shown.
export function membershipTermLines(subscription, formatDate = (d) => d) {
  if (!subscription) return []
  const ended = ['cancelled', 'expired', 'revoked'].includes(subscription.status)
  if (isLifetime(subscription)) {
    if (ended) return subscription.endedAt ? [`Ended ${formatDate(subscription.endedAt)}`] : ['Ended']
    return ['Lifetime access', 'No renewal required']
  }
  if (ended) return subscription.endedAt ? [`Ended ${formatDate(subscription.endedAt)}`] : []
  if (!subscription.currentPeriodEnd) return ['No automatic expiry']
  return [`${subscription.cancelAtPeriodEnd ? 'Access ends' : 'Renews or ends'} ${formatDate(subscription.currentPeriodEnd)}`]
}

// Admin list/detail: "Lifetime · No expiry" instead of a fabricated date.
export function adminPeriodText(subscription, formatDate = (d) => d) {
  if (isLifetime(subscription)) return 'Lifetime · No expiry'
  if (!subscription?.currentPeriodEnd) return 'No expiry set'
  return formatDate(subscription.currentPeriodEnd)
}
