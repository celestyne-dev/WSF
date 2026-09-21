// Static, human-readable labels/descriptions for the platform's RBAC
// roles — display metadata only, not content. The backend is the source
// of truth for which roles actually exist and what permissions they carry
// (GET /api/v1/admin/roles); this table only supplies a friendlier label
// than a raw role key like "partnerships_manager" wherever the UI shows
// one. This is a static constant, not something loaded from a database.
export const ROLE_DEFINITIONS = [
  { key: 'super_admin', label: 'Super Admin', description: 'Full access to every CMS area, including user management and site settings.' },
  { key: 'admin', label: 'Admin', description: 'Full content and commerce access, excluding user role management.' },
  { key: 'editor', label: 'Editor', description: 'Can create, edit, approve, and publish all editorial content.' },
  { key: 'author', label: 'Author', description: 'Can create and edit own articles; requires editor approval to publish.' },
  { key: 'moderator', label: 'Moderator', description: 'Reviews story submissions and nominations.' },
  { key: 'partnerships_manager', label: 'Partnerships Manager', description: 'Manages sponsors, partners, and partnership enquiries.' },
  { key: 'opportunities_manager', label: 'Opportunities Manager', description: 'Manages job, opportunity, and event listings.' },
  { key: 'events_manager', label: 'Events Manager', description: 'Manages event listings, agendas, and registrations.' },
  { key: 'analyst', label: 'Analyst', description: 'Read-only access to analytics dashboards.' },
  { key: 'member', label: 'Member', description: 'Registered reader with a public-facing account.' },
  { key: 'employer', label: 'Employer', description: 'Can submit and manage job and opportunity listings.' },
]

export function getRoleLabel(key) {
  return ROLE_DEFINITIONS.find((r) => r.key === key)?.label || key
}
