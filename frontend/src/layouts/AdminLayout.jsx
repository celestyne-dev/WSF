import { useEffect } from 'react'
import { NavLink, Outlet, Navigate, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { LogOut, ExternalLink } from 'lucide-react'
import { restoreSession, logout } from '../features/auth/authSlice'
import { getRoleLabel } from '../constants/roles'
import { NAV_GROUPS } from '../constants/adminNav'
import { hasPermission, hasCmsAccess, getDefaultCmsRoute } from '../utils/permissions'
import { canAccessAdminRoute } from '../utils/routeAccess'
import NotificationBell from '../components/cms/NotificationBell'

export default function AdminLayout() {
  const dispatch = useDispatch()
  const { user, accessToken } = useSelector((s) => s.auth)
  const location = useLocation()

  useEffect(() => {
    if (accessToken && !user) dispatch(restoreSession())
  }, [accessToken, user, dispatch])

  if (!accessToken) return <Navigate to="/login" replace />

  // A token exists but the user hasn't loaded yet (restoreSession in
  // flight) — render a loader instead of judging CMS access against a
  // still-empty user, which would incorrectly bounce a real CMS staff
  // member to "/" before their permissions arrive.
  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-taupe-100">
        <p className="text-sm text-charcoal-600">Loading…</p>
      </div>
    )
  }

  // A real member/employer account authenticated successfully but holds no
  // CMS permission — public accounts are not CMS staff no matter how they
  // got a valid token (see utils/permissions.js:hasCmsAccess).
  if (!hasCmsAccess(user)) return <Navigate to="/" replace />

  // Sidebar hiding only keeps unauthorized links out of view; someone can
  // still type /admin/users directly. Redirect to their own allowed area
  // instead of rendering a page whose API will just 403 the data calls.
  if (!canAccessAdminRoute(user, location.pathname)) {
    return <Navigate to={getDefaultCmsRoute(user)} replace />
  }

  const roleLabel = user?.role ? getRoleLabel(user.role) : null

  return (
    <div className="flex min-h-screen bg-taupe-100 text-charcoal">
      <aside className="hidden w-64 shrink-0 flex-col bg-charcoal-800 text-ivory lg:flex">
        <div className="flex h-16 items-center border-b border-ivory/10 px-6">
          <span className="font-serif text-lg font-semibold">WSF Studio</span>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {NAV_GROUPS.map((group) => {
            // A nonfunctional (403-on-open) admin menu item is worse than
            // no item, so every item whose page requires a permission is
            // hidden unless the account actually holds it. This is UX
            // only: the backend permission decorators are what actually
            // enforce access either way (see NAV_GROUPS's own comment).
            const visibleItems = group.items.filter((item) => !item.permission || hasPermission(user, ...item.permission))
            if (visibleItems.length === 0) return null
            return (
              <div key={group.heading} className="mb-5">
                <p className="px-3 text-[10px] font-semibold uppercase tracking-widest2 text-ivory/40">{group.heading}</p>
                <ul className="mt-1.5 space-y-0.5">
                  {visibleItems.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        end={item.end}
                        className={({ isActive }) =>
                          `flex items-center gap-2.5 px-3 py-2 text-sm font-medium transition-colors ${
                            isActive ? 'bg-burgundy-500/20 text-ivory' : 'text-ivory/70 hover:bg-ivory/5 hover:text-ivory'
                          }`
                        }
                      >
                        <item.icon size={16} />
                        {item.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </nav>
        <div className="border-t border-ivory/10 p-4">
          <a href="/" target="_blank" rel="noreferrer" className="flex items-center gap-2 px-2 py-1.5 text-xs text-ivory/60 hover:text-ivory">
            <ExternalLink size={13} /> View live site
          </a>
        </div>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-taupe-300 bg-white px-6">
          <p className="font-serif text-lg font-semibold text-charcoal lg:hidden">WSF Studio</p>
          <div className="hidden text-sm text-charcoal-600 lg:block">Content Management System</div>
          <div className="flex items-center gap-3">
            <NotificationBell />
            <div className="text-right text-sm">
              <p className="font-semibold text-charcoal">{user?.name || 'Loading…'}</p>
              <p className="text-xs text-charcoal-600">{roleLabel}</p>
            </div>
            <button
              type="button"
              onClick={() => dispatch(logout())}
              aria-label="Log out"
              className="flex h-9 w-9 items-center justify-center border border-taupe-300 text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
