import { NavLink, useLocation } from 'react-router-dom'
import { LayoutGrid, UserRound, Bookmark, CalendarDays, GraduationCap, Users, Sparkles, ShieldCheck, LogOut } from 'lucide-react'

const NAV_GROUPS = [
  {
    label: 'Account',
    items: [
      { to: '/account', label: 'Overview', end: true, icon: LayoutGrid },
      { to: '/account/profile', label: 'Profile', icon: UserRound },
      { to: '/account/saved', label: 'Saved', icon: Bookmark },
    ],
  },
  {
    label: 'Activity',
    items: [
      { to: '/account/events', label: 'My Events', icon: CalendarDays },
      { to: '/account/learning', label: 'My Learning', icon: GraduationCap },
    ],
  },
  {
    label: 'Memberships',
    items: [
      { to: '/account/community', label: 'WSF Community', icon: Users },
      { to: '/account/membership', label: 'WSF Circle', icon: Sparkles },
    ],
  },
  {
    label: 'Settings',
    items: [{ to: '/account/security', label: 'Security', icon: ShieldCheck }],
  },
]

const ALL_ITEMS = NAV_GROUPS.flatMap((group) => group.items)

function currentSectionLabel(pathname) {
  return ALL_ITEMS.find((item) => item.to === pathname)?.label || 'Overview'
}

function NavItem({ item, onNavigate }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `flex items-center gap-2.5 border-l-2 px-3 py-2 text-sm font-medium transition-colors ${
          isActive
            ? 'border-burgundy-600 bg-blush-50 text-burgundy-600'
            : 'border-transparent text-charcoal-600 hover:border-taupe-300 hover:text-charcoal'
        }`
      }
    >
      <Icon size={16} className="shrink-0" aria-hidden="true" />
      {item.label}
    </NavLink>
  )
}

function NavGroups({ onNavigate }) {
  return (
    <>
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="mb-5 last:mb-0">
          <p className="px-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600/60">{group.label}</p>
          <ul className="mt-1.5 space-y-0.5">
            {group.items.map((item) => (
              <li key={item.to}>
                <NavItem item={item} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  )
}

function SignOutButton({ onSignOut, className }) {
  return (
    <button type="button" onClick={onSignOut} className={className}>
      <LogOut size={16} className="shrink-0" aria-hidden="true" />
      Sign out
    </button>
  )
}

/**
 * Shared account navigation — a plain editorial rail on desktop/tablet
 * (sticky below the public header), collapsed into a native <details>
 * disclosure on mobile so eight nav items don't turn into a horizontal tab
 * strip. No new dependency: <details>/<summary> is keyboard-accessible
 * (focusable summary, Enter/Space toggles) out of the box.
 */
export default function AccountNavigation({ onSignOut }) {
  const location = useLocation()
  const currentLabel = currentSectionLabel(location.pathname)

  return (
    <>
      <nav aria-label="Account" className="hidden lg:block lg:sticky lg:top-32 lg:max-h-[calc(100vh-9rem)] lg:self-start lg:overflow-y-auto">
        <NavGroups />
        <div className="mt-2 border-t border-taupe-200 pt-4">
          <SignOutButton
            onSignOut={onSignOut}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-sm font-medium text-charcoal-600 transition-colors hover:text-burgundy-600"
          />
        </div>
      </nav>

      <details className="border border-taupe-200 bg-cream lg:hidden">
        <summary className="flex cursor-pointer select-none items-center justify-between px-4 py-3 text-sm font-semibold text-charcoal">
          <span>Account menu</span>
          <span className="text-charcoal-600">{currentLabel}</span>
        </summary>
        <div className="border-t border-taupe-200 px-2 py-3">
          <NavGroups />
          <div className="mt-2 border-t border-taupe-200 pt-3">
            <SignOutButton
              onSignOut={onSignOut}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm font-medium text-charcoal-600 transition-colors hover:text-burgundy-600"
            />
          </div>
        </div>
      </details>
    </>
  )
}
