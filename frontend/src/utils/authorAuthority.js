// Pure helpers for the public Author authority profile (Node-testable).
// Counts are derived server-side (app/services/author_authority.py) —
// never stored — and only non-zero ones are shown.

export function authorStatItems(counts) {
  const items = [
    [counts?.articles, 'Article', 'Articles'],
    [counts?.resources, 'Career Tool', 'Career Tools'],
    [counts?.courses, 'Course', 'Courses'],
  ]
  return items
    .filter(([n]) => Number.isInteger(n) && n > 0)
    .map(([n, one, many]) => ({ value: n, label: n === 1 ? one : many }))
}

// "Learn with Celestine" — the first word of the display name.
export function authorFirstName(name) {
  return (name || '').trim().split(/\s+/)[0] || ''
}

// Whether a bounded section should render at all (never an empty shell).
export function hasItems(list) {
  return Array.isArray(list) && list.length > 0
}
