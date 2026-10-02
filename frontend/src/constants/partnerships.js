// The eight paid commercial formats publicly described on both /advertise
// (as CMS-managed AdvertiseOfferings — see backend app/services/
// advertise.py's CANONICAL_OFFERINGS) and /partnerships ("Available
// Partnership Formats", see PartnershipsPage.jsx's buildFormats()). Kept
// as its own list so the public inquiry dropdown can group them under
// their own <optgroup> — see backend app/models/commerce.py's
// PAID_PARTNERSHIP_TYPES, which this must match exactly (a mismatch here
// means the backend's CHECK constraint rejects a value this dropdown
// offers). "Research Partnerships" (plural) is a distinct value from the
// broader "Research Partnership" (singular) below — not a typo.
export const PAID_PARTNERSHIP_TYPES = [
  'Sponsored Editorial',
  'Sponsored Series',
  'Newsletter Sponsorship',
  'Social Media Campaigns',
  'Employer Branding',
  'Event Sponsorship',
  'Sponsored Resources',
  'Research Partnerships',
]

// Broader, non-paid-specific partnership categories — unchanged from
// before the paid formats above were added.
export const OTHER_PARTNERSHIP_TYPES = [
  'Brand Partnership',
  'Content Partnership',
  'Employer Partnership',
  'Event Partnership',
  'Community Partnership',
  'Education Partnership',
  'Resource Partnership',
  'Recruitment Partnership',
  'Strategic Partnership',
  'Affiliate Partnership',
  'Research Partnership',
  // Submitted by the public Advertise inquiry form — reuses this same
  // partnership pipeline rather than a second inquiry system.
  'Advertising',
  'Other',
]

// Flat, complete list — used by AdminPartnerships/AdminPartnershipDetail
// filters and edit screens (order doesn't matter there) and as the
// source of the public dropdown's default selection.
export const PARTNERSHIP_TYPES = [...PAID_PARTNERSHIP_TYPES, ...OTHER_PARTNERSHIP_TYPES]

export const PARTNERSHIP_STATUSES = [
  'new',
  'reviewing',
  'contacted',
  'qualified',
  'proposal',
  'negotiating',
  'active',
  'completed',
  'declined',
  'archived',
]
