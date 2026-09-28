// Mirrors backend app/models/directory.py's controlled vocabularies exactly
// — see that module's docstrings for why each of these is deliberately
// narrow (never inferred, never silently upgraded).

export const DIRECTORY_LISTING_TYPES = ['business', 'nonprofit', 'professional_service', 'social_enterprise', 'association']

export const DIRECTORY_LISTING_TYPE_LABELS = {
  business: 'Business',
  nonprofit: 'Nonprofit',
  professional_service: 'Professional service',
  social_enterprise: 'Social enterprise',
  association: 'Professional association',
}

export const DIRECTORY_OWNERSHIP_CLASSIFICATIONS = ['women_owned', 'women_led', 'women_founded', 'women_focused', 'unspecified']

export const DIRECTORY_OWNERSHIP_LABELS = {
  women_owned: 'Women-owned',
  women_led: 'Women-led',
  women_founded: 'Women-founded',
  women_focused: 'Women-focused',
  unspecified: 'Not specified',
}

export const DIRECTORY_VERIFICATION_STATUSES = ['unverified', 'self_attested', 'reviewed', 'verified']

export const DIRECTORY_VERIFICATION_LABELS = {
  unverified: 'Unverified',
  self_attested: 'Self-attested',
  reviewed: 'Reviewed by WSF',
  verified: 'Verified by WSF',
}

// Shown alongside the "Verified" badge so it's never mistaken for a
// government, legal, or financial certification — an internal WSF check
// only (see backend DIRECTORY_VERIFICATION_STATUSES docstring).
export const DIRECTORY_VERIFIED_EXPLANATION =
  'WSF staff reviewed this listing’s information for plausibility. This is not a legal, financial, or government certification.'

export const DIRECTORY_LISTING_STATUSES = ['pending', 'under_review', 'approved', 'published', 'rejected', 'archived']

export const DIRECTORY_LISTING_STATUS_LABELS = {
  pending: 'Pending',
  under_review: 'Under review',
  approved: 'Approved',
  published: 'Published',
  rejected: 'Rejected',
  archived: 'Archived',
}

export const DIRECTORY_SERVICE_MODES = ['local', 'national', 'international', 'remote', 'online', 'in_person']

export const DIRECTORY_SERVICE_MODE_LABELS = {
  local: 'Local',
  national: 'National',
  international: 'International',
  remote: 'Remote',
  online: 'Online',
  in_person: 'In person',
}

export const DIRECTORY_SUBMISSION_STATUSES = ['new', 'matched', 'duplicate', 'converted', 'rejected']

export const DIRECTORY_SUBMISSION_STATUS_LABELS = {
  new: 'New',
  matched: 'Matched',
  duplicate: 'Possible duplicate',
  converted: 'Converted',
  rejected: 'Rejected',
}
