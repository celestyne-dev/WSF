// Route-level UX guard for direct /admin/* URL entry — sidebar hiding alone
// doesn't stop someone from typing a URL. This is built from the exact same
// NAV_GROUPS data the sidebar renders (constants/adminNav.js), so a route
// can never be reachable directly while staying hidden from the menu, or
// vice versa. It does not duplicate backend authorization: the backend's
// own permission_required() decorators remain the real enforcement and
// still return 403 regardless of what this says.
import { NAV_GROUPS } from '../constants/adminNav'
import { hasPermission } from './permissions'

// Flattened once, longest route first, so a more specific route (e.g.
// /admin/directory/listings) is matched before a shorter one that happens
// to share a prefix (e.g. /admin/directory). The literal "/admin" dashboard
// entry is excluded here and checked separately below, since as a 6-char
// prefix it would otherwise "match" every other /admin/* path too.
const ROUTE_ITEMS = NAV_GROUPS.flatMap((group) => group.items)
  .filter((item) => item.to !== '/admin')
  .sort((a, b) => b.to.length - a.to.length)

export function canAccessAdminRoute(user, pathname) {
  if (user?.permissions?.includes('*')) return true
  if (pathname === '/admin') return hasPermission(user, 'analytics.view')
  const item = ROUTE_ITEMS.find((candidate) => pathname.startsWith(candidate.to))
  if (!item?.permission) return true // no mapped permission for this route — any CMS user, or not a nav route we guard
  return hasPermission(user, ...item.permission)
}
