import fs from 'fs'

const files = [
  'src/mock/jobs.js',
  'src/mock/opportunities.js',
  'src/mock/events.js',
  'src/mock/newsletter.js',
  'src/mock/articles.js',
  'src/mock/admin.js',
]

const FIELD_NAMES = [
  'publishDate', 'updatedDate', 'deadline', 'date', 'sendDate', 'startDate', 'endDate',
  'submittedAt', 'lastLogin', 'scheduledFor', 'expiryDate', 'publishedDate',
]

const fieldPattern = new RegExp(`(\\b(?:${FIELD_NAMES.join('|')})\\s*:\\s*['"])(\\d{4}-\\d{2}-\\d{2})((?:T[\\d:]+Z)?['"])`, 'g')

function shiftDate(dateStr, monthsToAdd) {
  const [y, m, d] = dateStr.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d))
  date.setUTCMonth(date.getUTCMonth() + monthsToAdd)
  const ny = date.getUTCFullYear()
  const nm = String(date.getUTCMonth() + 1).padStart(2, '0')
  const nd = String(date.getUTCDate()).padStart(2, '0')
  return `${ny}-${nm}-${nd}`
}

const MONTHS_SHIFT = 7

for (const file of files) {
  let content = fs.readFileSync(file, 'utf8')
  content = content.replace(fieldPattern, (match, prefix, datePart, suffix) => {
    const shifted = shiftDate(datePart, MONTHS_SHIFT)
    return `${prefix}${shifted}${suffix}`
  })
  fs.writeFileSync(file, content)
  console.log('Updated', file)
}
