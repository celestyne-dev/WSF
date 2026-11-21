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
