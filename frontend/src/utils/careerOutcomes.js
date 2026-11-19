// The public credit a Career Outcome will carry. Mirrors backend
// app/services/career_outcomes.py _attribution (server stays authoritative).
export function outcomePublicCredit(attribution, firstName, lastName) {
  if (attribution === 'first_name') {
    const first = (firstName || '').trim()
    const initial = (lastName || '').trim().slice(0, 1)
    if (first) return initial ? `${first} ${initial}.` : first
  }
  return 'A WSF community member'
}
