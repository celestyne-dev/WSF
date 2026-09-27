// Static, human-readable labels/descriptions for the platform's RBAC
// roles — display metadata only, not content. The backend is the source
// of truth for which roles actually exist and what permissions they carry
// (GET /api/v1/admin/roles); this table only supplies a friendlier label
// than a raw role key like "partnerships_manager" wherever the UI shows
// one. This is a static constant, not something loaded from a database.
export const ROLE_DEFINITIONS = [
  { key: 'super_admin', label: 'Super Admin', description: 'Full access to every CMS area, including user and role management. Cannot be locked out — the last active Super Admin is always protected.' },
  { key: 'admin', label: 'Admin', description: 'Full content and commerce access, including staff user management — but cannot grant or remove the Super Admin role.' },
  { key: 'editor', label: 'Editor', description: 'Can create, edit, approve, and publish all editorial content.' },
  { key: 'author', label: 'Author', description: 'Can create and edit own articles; requires editor approval to publish.' },
  { key: 'moderator', label: 'Moderator', description: 'Reviews story submissions and nominations, and administers community membership.' },
  { key: 'partnerships_manager', label: 'Partnerships Manager', description: 'Manages sponsors, partners, and partnership enquiries; sees commercial analytics.' },
  { key: 'opportunities_manager', label: 'Opportunities Manager', description: 'Manages job and opportunity listings.' },
  { key: 'events_manager', label: 'Events Manager', description: 'Manages event listings, agendas, and registrations.' },
  { key: 'products_manager', label: 'Products Manager', description: 'Manages the shop catalog.' },
  { key: 'orders_manager', label: 'Orders Manager', description: 'Manages customer orders.' },
  { key: 'resources_manager', label: 'Resources Manager', description: 'Manages the resource library.' },
  { key: 'newsletter_manager', label: 'Newsletter Manager', description: 'Manages newsletter issues and subscribers (not bulk export).' },
  { key: 'community_manager', label: 'Community Manager', description: 'Administers community membership, including data export.' },
  { key: 'mentorship_manager', label: 'Mentorship Manager', description: 'Manages mentorship programs, applications, and matches.' },
  { key: 'submissions_manager', label: 'Submissions Manager', description: 'Reviews story submissions.' },
  { key: 'nominations_manager', label: 'Nominations Manager', description: 'Reviews nominations.' },
  { key: 'taxonomy_manager', label: 'Taxonomy Manager', description: 'Manages topics, categories, series, and tags.' },
  { key: 'pages_manager', label: 'Pages Manager', description: 'Manages static site pages.' },
  { key: 'homepage_manager', label: 'Homepage Manager', description: 'Manages the homepage module layout.' },
  { key: 'navigation_manager', label: 'Navigation Manager', description: 'Manages site navigation menus.' },
  { key: 'footer_manager', label: 'Footer Manager', description: 'Manages footer content and links.' },
  { key: 'analyst', label: 'Analyst', description: 'Read-only access to analytics dashboards (not commercial data).' },
  { key: 'member', label: 'Member', description: 'Registered reader with a public-facing account — not a CMS staff role.' },
  { key: 'employer', label: 'Employer', description: 'Can submit and manage job and opportunity listings — not a CMS staff role.' },
]

export function getRoleLabel(key) {
  return ROLE_DEFINITIONS.find((r) => r.key === key)?.label || key
}
