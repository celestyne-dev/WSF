// Client-side permission helpers — UX only (hide a nav item, don't render
// a button). The backend's permission_required()/roles_required()
// decorators (app/auth/decorators.py) are the sole source of truth for
// what an action is actually allowed to do; nothing here can substitute
// for that, and every mutating admin request is still rejected
// server-side even if a stale or tampered client thinks it's allowed.
//
// `user.permissions` is the flattened set of every permission granted by
// every role the account holds (see api/auth.js:mapUser) — "*" is the
// super_admin wildcard, mirroring the backend's own seed_roles_and_
// permissions() grant.
export function hasPermission(user, ...permissionNames) {
  if (!user?.permissions) return false
  if (user.permissions.includes('*')) return true
  return permissionNames.some((name) => user.permissions.includes(name))
}

export function hasRole(user, ...roleNames) {
  if (!user?.roles) return false
  return roleNames.some((name) => user.roles.includes(name))
}
