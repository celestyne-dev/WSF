// Mirrors backend app/models/people.py WORKPLACE_PRACTICES /
// WORKPLACE_CLAIM_SOURCES and app/models/submissions.py
// CAREER_OUTCOME_TYPES (kept in sync by convention, like RESERVED_SLUGS).

export const WORKPLACE_PRACTICES = [
  { value: 'flexible_work', label: 'Flexible working' },
  { value: 'remote_work', label: 'Remote working' },
  { value: 'paid_parental_leave', label: 'Paid parental leave' },
  { value: 'pay_transparency', label: 'Pay transparency' },
  { value: 'pay_equity_review', label: 'Pay equity review' },
  { value: 'women_leadership_program', label: 'Women’s leadership programme' },
  { value: 'mentorship_program', label: 'Mentorship programme' },
  { value: 'return_to_work_program', label: 'Return-to-work programme' },
  { value: 'childcare_support', label: 'Childcare support' },
  { value: 'anti_harassment_policy', label: 'Anti-harassment policy' },
  { value: 'menopause_support', label: 'Menopause support' },
]

// Where a claim comes from. Never a certification by WSF.
export const WORKPLACE_CLAIM_SOURCES = [
  { value: 'self_reported', label: 'Self-reported by the employer' },
  { value: 'publicly_documented', label: 'Publicly documented' },
  { value: 'wsf_reviewed', label: 'Source reviewed by WSF' },
]

export const CAREER_OUTCOME_TYPES = [
  { value: 'new_job', label: 'Landed a new job' },
  { value: 'promotion', label: 'Got promoted' },
  { value: 'pay_increase', label: 'Negotiated a pay increase' },
  { value: 'career_change', label: 'Changed careers' },
  { value: 'returned_to_work', label: 'Returned to work' },
  { value: 'started_business', label: 'Started a business' },
  { value: 'leadership_role', label: 'Stepped into leadership' },
  { value: 'new_qualification', label: 'Earned a new qualification' },
]

export function labelFor(options, value) {
  return options.find((o) => o.value === value)?.label || null
}
