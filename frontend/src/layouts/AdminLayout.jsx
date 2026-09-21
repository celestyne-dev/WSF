import { useEffect } from 'react'
import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  LayoutDashboard,
  Newspaper,
  Users,
  Briefcase,
  Award,
  CalendarDays,
  BookOpen,
  Mail,
  Inbox,
  Star,
  Handshake,
  Megaphone,
  Image,
  Search,
  BarChart3,
  Settings,
  LogOut,
  ExternalLink,
  LayoutTemplate,
} from 'lucide-react'
import { restoreSession, logout } from '../features/auth/authSlice'
import { getRoleLabel } from '../constants/roles'

const NAV_GROUPS = [
  {
    heading: 'Overview',
    items: [{ to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true }],
  },
  {
    heading: 'Content',
    items: [
      { to: '/admin/articles', icon: Newspaper, label: 'Articles' },
      { to: '/admin/homepage', icon: LayoutTemplate, label: 'Homepage' },
      { to: '/admin/people', icon: Users, label: 'People' },
    ],
  },
  {
    heading: 'Opportunity',
    items: [
      { to: '/admin/jobs', icon: Briefcase, label: 'Jobs' },
      { to: '/admin/opportunities', icon: Award, label: 'Opportunities' },
      { to: '/admin/events', icon: CalendarDays, label: 'Events' },
      { to: '/admin/resources', icon: BookOpen, label: 'Resources' },
    ],
  },
  {
    heading: 'Community',
    items: [
      { to: '/admin/newsletter', icon: Mail, label: 'Newsletter' },
      { to: '/admin/submissions', icon: Inbox, label: 'Submissions' },
      { to: '/admin/nominations', icon: Star, label: 'Nominations' },
    ],
  },
  {
    heading: 'Revenue',
    items: [
      { to: '/admin/partnerships', icon: Handshake, label: 'Partnerships' },
      { to: '/admin/advertising', icon: Megaphone, label: 'Advertising' },
    ],
  },
  {
    heading: 'System',
    items: [
      { to: '/admin/media', icon: Image, label: 'Media Library' },
      { to: '/admin/seo', icon: Search, label: 'SEO' },
      { to: '/admin/analytics', icon: BarChart3, label: 'Analytics' },
      { to: '/admin/users', icon: Users, label: 'Users & Roles' },
      { to: '/admin/settings', icon: Settings, label: 'Settings' },
    ],
  },
]

export default function AdminLayout() {
  const dispatch = useDispatch()
  const { user, accessToken } = useSelector((s) => s.auth)

  useEffect(() => {
    if (accessToken && !user) dispatch(restoreSession())
  }, [accessToken, user, dispatch])

  if (!accessToken) return <Navigate to="/login" replace />

  const roleLabel = user?.role ? getRoleLabel(user.role) : null

  return (
    <div className="flex min-h-screen bg-taupe-100 text-charcoal">
      <aside className="hidden w-64 shrink-0 flex-col bg-charcoal-800 text-ivory lg:flex">
        <div className="flex h-16 items-center border-b border-ivory/10 px-6">
          <span className="font-serif text-lg font-semibold">WSF Studio</span>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.heading} className="mb-5">
              <p className="px-3 text-[10px] font-semibold uppercase tracking-widest2 text-ivory/40">{group.heading}</p>
              <ul className="mt-1.5 space-y-0.5">
                {group.items.map((item) => (
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
          ))}
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
