// WSF Career Hub metadata vocabulary for WSF Studio — mirrors the backend
// controlled values (app/models/resource.py RESOURCE_TYPES +
// ESTIMATED_TIME_UNITS, app/models/learning.py LEARNING_PROGRAM_TYPES,
// app/models/taxonomy.py CAREER_GOALS). Stored values never change;
// only the friendly labels live here.

// Resource "format" — stored on Resource.type (title-case values).
export const RESOURCE_FORMAT_OPTIONS = [
  { value: 'Playbook', label: 'Playbook' },
  { value: 'Workbook', label: 'Workbook' },
  { value: 'Toolkit', label: 'Toolkit' },
  { value: 'Checklist', label: 'Checklist' },
  { value: 'Scripts', label: 'Scripts' },
  { value: 'Template', label: 'Template' },
  { value: 'Planner', label: 'Planner' },
  { value: 'Guide', label: 'Guide' },
  { value: 'Challenge', label: 'Challenge' },
  { value: 'Assessment', label: 'Assessment' },
  { value: 'Research', label: 'Research' },
  { value: 'Report', label: 'Report' },
  { value: 'Ebook', label: 'eBook' },
  { value: 'Other', label: 'Other' },
]

// Older values kept valid so existing Resources stay editable; not offered
// as Career Hub formats (they appear there as "Other", never as video).
export const LEGACY_RESOURCE_TYPE_OPTIONS = [
  { value: 'Worksheet', label: 'Worksheet' },
  { value: 'Download', label: 'Download (legacy)' },
  { value: 'Video Resource', label: 'Video Resource (legacy)' },
  { value: 'External Resource', label: 'External Resource (legacy)' },
]

export const ALL_RESOURCE_TYPE_OPTIONS = [...RESOURCE_FORMAT_OPTIONS, ...LEGACY_RESOURCE_TYPE_OPTIONS]

export function resourceTypeLabel(value) {
  return ALL_RESOURCE_TYPE_OPTIONS.find((o) => o.value === value)?.label || value || ''
}

export const LEARNING_PROGRAM_TYPE_OPTIONS = [
  { value: 'course', label: 'Course' },
  { value: 'masterclass', label: 'Masterclass' },
  { value: 'program', label: 'Program' },
  { value: 'learning_series', label: 'Learning Series' },
  { value: 'challenge', label: 'Challenge' },
]

export const LEARNING_PROGRAM_TYPE_LABEL = Object.fromEntries(LEARNING_PROGRAM_TYPE_OPTIONS.map((o) => [o.value, o.label]))

// "How long should a reader expect to spend using/completing this?" —
// not video duration.
export const ESTIMATED_TIME_UNIT_OPTIONS = [
  { value: 'minutes', label: 'Minutes' },
  { value: 'hours', label: 'Hours' },
  { value: 'days', label: 'Days' },
  { value: 'weeks', label: 'Weeks' },
  { value: 'self_paced', label: 'Self-paced (no fixed time)' },
]

export const CAREER_GOAL_OPTIONS = [
  { value: 'find_a_job', label: 'Find a job' },
  { value: 'get_promoted', label: 'Get promoted' },
  { value: 'earn_more', label: 'Earn more' },
  { value: 'build_visibility', label: 'Build visibility' },
  { value: 'leadership', label: 'Lead better' },
  { value: 'career_change', label: 'Change careers' },
  { value: 'return_to_work', label: 'Return to work' },
  { value: 'networking', label: 'Network better' },
  { value: 'workplace_challenges', label: 'Handle workplace challenges' },
  { value: 'productivity', label: 'Work smarter' },
  { value: 'confidence', label: 'Build confidence' },
  { value: 'ai_at_work', label: 'Use AI at work' },
  { value: 'entrepreneurship', label: 'Grow a business' },
]
