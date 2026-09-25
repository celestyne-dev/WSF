export const SUBMISSION_STATUSES = [
  'submitted', 'reviewing', 'needs_information', 'shortlisted', 'approved',
  'converted', 'published', 'declined', 'withdrawn', 'archived',
]

export const STORY_TYPES = [
  'personal_story', 'career_journey', 'leadership_story', 'founder_story',
  'business_story', 'community_impact', 'starting_again', 'overcoming_barriers',
  'women_doing_incredible_things', 'women_leading_organizations', 'workplace_story',
  'opportunity_achievement', 'other',
]

export const STORY_TYPE_LABELS = {
  personal_story: 'Personal story',
  career_journey: 'Career journey',
  leadership_story: 'Leadership story',
  founder_story: 'Founder story',
  business_story: 'Business story',
  community_impact: 'Community impact',
  starting_again: 'Starting again / reinvention',
  overcoming_barriers: 'Overcoming barriers',
  women_doing_incredible_things: 'Women Doing Incredible Things',
  women_leading_organizations: 'Women Leading Organizations',
  workplace_story: 'Workplace story',
  opportunity_achievement: 'Opportunity / achievement story',
  other: 'Other',
}

export const CONTENT_ORIGINS = ['first_person', 'on_behalf_of', 'previously_published', 'adapted']

export const CONTENT_ORIGIN_LABELS = {
  first_person: 'Written by me, first-person',
  on_behalf_of: 'Submitted on behalf of someone else',
  previously_published: 'Previously published elsewhere',
  adapted: 'Adapted from another source',
}

export const AI_INVOLVEMENT_VALUES = ['none', 'ai_assisted', 'ai_generated_reviewed']

export const AI_INVOLVEMENT_LABELS = {
  none: 'Written entirely by me',
  ai_assisted: 'AI-assisted (helped with research, editing, or suggestions)',
  ai_generated_reviewed: 'Substantially AI-generated, then reviewed and edited by me',
}

export const VERIFICATION_STATUSES = ['unverified', 'verification_needed', 'verified']

export const SUBJECT_PERMISSION_STATUSES = ['not_applicable', 'unknown', 'needs_confirmation', 'confirmed']
