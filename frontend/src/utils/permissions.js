// Client-side permission helpers — UX only (hide a nav item, don't render
// a button). The backend's permission_required()/roles_required()
// decorators (app/auth/decorators.py) are the sole source of truth for
// what an action is actually allowed to do; nothing here can substitute
// for that, and every mutating admin request is still rejected
// server-side even if a stale or tampered client thinks it's allowed.
//
// `user.permissions` is the flattened set of every permission granted by
// every role the account holds (see api/auth.js:mapUser). "*" is checked
// as a super_admin wildcard for mock mode (mapMockUser); the real backend
// never sends that literal — seed_roles_and_permissions() instead grants
// super_admin every individual Permission row, so a real super_admin's
// `permissions` already contains every name and every hasPermission()
// check below passes through the normal `.some()` match regardless.
export function hasPermission(user, ...permissionNames) {
  if (!user?.permissions) return false
  if (user.permissions.includes('*')) return true
  return permissionNames.some((name) => user.permissions.includes(name))
}

export function hasRole(user, ...roleNames) {
  if (!user?.roles) return false
  return roleNames.some((name) => user.roles.includes(name))
}

// Permissions a public (member/employer) account can hold that must NOT by
// themselves grant CMS access — see app/services/rbac.py's ROLE_PERMISSIONS
// for "member" (profile.manage) and "employer" (jobs.create_own). Every
// other permission name is a staff/editorial one.
const PUBLIC_ONLY_PERMISSIONS = ['profile.manage', 'jobs.create_own']

export function hasCmsAccess(user) {
  if (!user?.permissions?.length) return false
  if (user.permissions.includes('*')) return true
  return user.permissions.some((name) => !PUBLIC_ONLY_PERMISSIONS.includes(name))
}

// Ordered permission -> CMS route map used to pick a default landing route
// right after login (getDefaultCmsRoute below). This is deliberately a
// curated subset — one entry per feature area, not every /admin/* sub-page
// — unlike utils/routeAccess.js's direct-URL guard, which is built from the
// full sidebar list in constants/adminNav.js. Each permission here was
// verified against the real @permission_required(...)/has_permission() gate
// on that section's backend API (app/api/v1/*.py), not guessed from the
// route's name — see constants/adminNav.js's own audit notes.
export const CMS_ROUTE_PERMISSIONS = [
  { route: '/admin/articles', permissions: ['articles.manage', 'articles.edit_own'] },
  { route: '/admin/people', permissions: ['people.manage'] },
  { route: '/admin/authors', permissions: ['people.manage'] },
  { route: '/admin/organizations', permissions: ['people.manage'] },
  { route: '/admin/pages', permissions: ['pages.manage'] },
  { route: '/admin/taxonomy/topics', permissions: ['taxonomy.manage'] },
  { route: '/admin/homepage', permissions: ['homepage.manage'] },
  { route: '/admin/navigation', permissions: ['navigation.manage'] },
  { route: '/admin/footer', permissions: ['footer.manage'] },
  { route: '/admin/members', permissions: ['community.manage'] },
  { route: '/admin/newsletter', permissions: ['newsletter.manage'] },
  { route: '/admin/mentorship', permissions: ['mentorship.manage'] },
  { route: '/admin/submissions', permissions: ['submissions.manage'] },
  { route: '/admin/nominations', permissions: ['nominations.manage'] },
  { route: '/admin/contact', permissions: ['contact.manage'] },
  { route: '/admin/partnerships', permissions: ['partnerships.manage'] },
  { route: '/admin/opportunities', permissions: ['opportunities.manage'] },
  { route: '/admin/jobs', permissions: ['jobs.manage'] },
  { route: '/admin/events', permissions: ['events.manage'] },
  { route: '/admin/resources', permissions: ['resources.manage'] },
  { route: '/admin/products', permissions: ['products.manage'] },
  { route: '/admin/directory/listings', permissions: ['directory.manage'] },
  { route: '/admin/learning', permissions: ['learning.manage'] },
  { route: '/admin/media', permissions: ['media.manage', 'media.upload'] },
  { route: '/admin/analytics', permissions: ['analytics.view', 'analytics.commercial'] },
  { route: '/admin/users', permissions: ['users.view', 'users.manage', 'roles.manage'] },
  { route: '/admin/audit', permissions: ['audit.view'] },
  { route: '/admin/settings', permissions: ['settings.manage'] },
]

// Where a user lands right after login, and the fallback target when they
// open an /admin/* route their permissions don't cover (see routeAccess.js).
// Super Admin would otherwise match the very first entry below (Articles) —
// checked by role name rather than the "*" wildcard because the real
// backend never actually sends that literal: seed_roles_and_permissions()
// (app/services/rbac.py) grants super_admin every individual Permission
// row, so mapUser() (api/auth.js) flattens it into the full enumerated
// list, not a single "*" string — "*" only ever appears from mapMockUser.
export function getDefaultCmsRoute(user) {
  if (!hasCmsAccess(user)) return '/'
  if (user.permissions.includes('*') || hasRole(user, 'super_admin')) return '/admin'
  const match = CMS_ROUTE_PERMISSIONS.find((entry) => hasPermission(user, ...entry.permissions))
  return match ? match.route : '/admin'
}
