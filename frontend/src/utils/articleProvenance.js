// Studio <-> API shape for an Article's structured provenance rows
// (backend app/services/article_experts.py). A row is a recorded role
// pointing at an existing Author or Person ("author:slug" / "person:slug").
export const EXPERT_ROLES = [
  { value: 'reviewed_by', label: 'Reviewed by' },
  { value: 'fact_checked_by', label: 'Fact checked by' },
  { value: 'expert_contributor', label: 'Expert contribution by' },
]

export function expertRowsToPayload(rows) {
  return (rows || [])
    .filter((r) => r.role && r.profile)
    .map((r) => {
      const [kind, slug] = r.profile.split(':')
      return kind === 'author' ? { role: r.role, authorSlug: slug } : { role: r.role, personSlug: slug }
    })
}

export function expertRowsFromArticle(refs) {
  return (refs || []).map((r) => ({ role: r.role, profile: r.authorSlug ? `author:${r.authorSlug}` : `person:${r.personSlug}` }))
}

// "Updated" is shown only when an editor recorded it, it is not in the future
// and it is after publication (backend article_experts.is_displayable_update).
export function isDisplayableUpdate(updatedAt, publishDate, now = new Date()) {
  if (!updatedAt) return false
  const updated = new Date(updatedAt)
  if (Number.isNaN(updated.getTime()) || updated > now) return false
  return !publishDate || updated > new Date(publishDate)
}

// The Studio date input's maximum (today, local): convenience only; the API
// rejects a future date whatever the browser sends.
export function todayInputValue(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// A chosen calendar day -> the timestamp sent to the API: today means "now"
// (so it is never in the future), an earlier day means midday local time.
export function editorialUpdatedAtToPayload(day, now = new Date()) {
  if (!day) return null
  if (day === todayInputValue(now)) return now.toISOString()
  return new Date(`${day}T12:00:00`).toISOString()
}
