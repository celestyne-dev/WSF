export function formatDate(dateStr, options = { month: 'long', day: 'numeric', year: 'numeric' }) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', options)
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
