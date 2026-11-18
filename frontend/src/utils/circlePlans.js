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
  if (plan?.billingInterval === 'lifetime') return 'One payment · no renewal'
  return plan?.billingInterval === 'yearly' ? 'Best annual value' : 'Flexible access'
}

// One sentence per interval actually offered — never mentions a plan type
// that isn't configured. Mirrors spa_shell.py's _circle_plan_guidance().
export function planGuidance(plans) {
  const intervals = new Set((plans || []).map((p) => p.billingInterval))
  const parts = []
  if (intervals.has('monthly')) parts.push('Choose Monthly for flexibility.')
  if (intervals.has('yearly')) parts.push('Choose Yearly for the best annual value and exclusive annual-member bonuses.')
  if (intervals.has('lifetime')) parts.push('Choose Lifetime for one payment and permanent access to WSF Circle membership benefits — no renewal.')
  return parts.join(' ')
}

// Benefits heading for plans whose members get the annual-member bonuses.
export function planExtrasHeading(plan) {
  if (plan?.billingInterval === 'lifetime') return 'Lifetime member benefits'
  if (plan?.billingInterval === 'yearly') return 'Yearly member extras'
  return null
}

export const LIFETIME_SCOPE_NOTE =
  'Lifetime access to WSF Circle membership benefits. Separately sold programmes, coaching, events and products are not included.'

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
