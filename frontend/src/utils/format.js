export function formatDate(dateStr, options = { month: 'long', day: 'numeric', year: 'numeric' }) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', options)
}

// Coarse "how long ago" for the Admin Notifications inbox/bell — every
// backend timestamp is UTC (see the model's `server_default=db.func.now()`
// columns) and `Date` parses that + renders relative deltas without
// assuming any particular viewer timezone, so no Kenya-specific offset is
// hardcoded here. Falls back to formatDate for anything a week or older,
// where a relative label stops being useful at a glance.
export function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const then = new Date(dateStr)
  const diffSeconds = Math.round((Date.now() - then.getTime()) / 1000)
  if (diffSeconds < 60) return 'Just now'
  const diffMinutes = Math.round(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.round(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateStr)
}

export function formatShortDate(dateStr) {
  return formatDate(dateStr, { month: 'short', day: 'numeric' })
}

export function formatDeadline(dateStr) {
  const date = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.ceil((date - now) / (1000 * 60 * 60 * 24))
  if (diffDays < 0) return 'Closed'
  if (diffDays === 0) return 'Closes today'
  if (diffDays <= 14) return `Closes in ${diffDays} day${diffDays === 1 ? '' : 's'}`
  return `Closes ${formatDate(dateStr)}`
}

export function formatSalary(job) {
  if (!job.salaryMin && !job.salaryMax) return 'Salary not disclosed'
  const fmt = (n) => new Intl.NumberFormat('en-US').format(n)
  if (job.salaryMin && job.salaryMax) {
    return `${job.currency} ${fmt(job.salaryMin)}–${fmt(job.salaryMax)}/${job.salaryPeriod}`
  }
  return `${job.currency} ${fmt(job.salaryMin || job.salaryMax)}/${job.salaryPeriod}`
}

export function formatCurrency(amount, currency = 'KES') {
  if (!amount) return 'Free'
  return `${currency} ${new Intl.NumberFormat('en-US').format(amount)}`
}

// Shop product pricing: zero displays as "Free" rather than "$0.00", and a
// real currency symbol/code is rendered via Intl.NumberFormat instead of
// manually concatenating one, so USD/GBP/EUR get their native symbol and a
// currency without one (KES) falls back to its ISO code automatically.
export function formatProductPrice(amount, currency = 'USD') {
  if (amount === null || amount === undefined) return null
  if (amount === 0) return 'Free'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${new Intl.NumberFormat('en-US').format(amount)}`
  }
}

// Only ever called with real, already-validated price/salePrice values —
// never fabricates a discount when sale_price is missing or not lower than
// the regular price.
export function formatDiscountPercent(price, salePrice) {
  if (!price || salePrice == null || salePrice >= price) return null
  return Math.round(((price - salePrice) / price) * 100)
}

// Prefers the free-text funding summary an editor wrote (handles compound
// cases like "Full tuition + $2,000 stipend" that a number range can't
// express); falls back to a structured min/max/currency range; returns
// null when the opportunity genuinely carries no funding data rather than
// fabricating a value.
export function formatFunding(opportunity) {
  if (!opportunity) return null
  if (opportunity.fundingValue) return opportunity.fundingValue
  const { fundingMin, fundingMax, currency } = opportunity
  if (fundingMin == null && fundingMax == null) return null
  const fmt = (n) => new Intl.NumberFormat('en-US').format(n)
  const prefix = currency ? `${currency} ` : ''
  if (fundingMin != null && fundingMax != null && fundingMin !== fundingMax) {
    return `${prefix}${fmt(fundingMin)}–${fmt(fundingMax)}`
  }
  return `${prefix}${fmt(fundingMin ?? fundingMax)}`
}
