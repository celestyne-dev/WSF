import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { ArrowRight, ChevronDown, X } from 'lucide-react'
import Logo from './Logo'
import NavDestination from './NavDestination'
import { NAV_ICONS } from './navIcons'
import { toggleMobileNav } from '../../features/navigation/uiSlice'
import { logoutUser } from '../../features/auth/authSlice'
import { hasCmsAccess, getDefaultCmsRoute } from '../../utils/permissions'
import { buildHeaderNavigation } from '../../utils/megaMenu'

const subLinkClass = 'flex items-start gap-3 rounded-lg py-2 text-[15px] text-charcoal hover:text-burgundy-600'
const accountLinkClass = 'block py-2 text-sm font-medium text-charcoal-600 hover:text-burgundy-600'

// Below `xl`: an accordion of the SAME header model the desktop mega menus
// use (utils/megaMenu.js), so mobile and desktop never drift apart. One
// group open at a time; any link closes the menu.
export default function MobileNav() {
  const open = useSelector((s) => s.ui.mobileNavOpen)
  const navigation = useSelector((s) => s.site.navigation)
  const user = useSelector((s) => s.auth.user)
  const accessToken = useSelector((s) => s.auth.accessToken)
  // Same rules as AccountMenu; Studio waits for `user` permissions.
  const isAuthenticated = Boolean(user || accessToken)
  const studioHref = user && hasCmsAccess(user) ? getDefaultCmsRoute(user) : null
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(null)
  const entries = useMemo(() => buildHeaderNavigation(navigation), [navigation])

  if (!open) return null
  const socialLinks = navigation?.social || []

  function close() {
    dispatch(toggleMobileNav(false))
  }

  function signOut() {
    dispatch(logoutUser())
    close()
    navigate('/')
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ivory xl:hidden" role="dialog" aria-modal="true" aria-label="Site menu">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-taupe-200 px-4">
        <div onClickCapture={close}>
          <Logo />
        </div>
        <button type="button" onClick={close} aria-label="Close menu" className="p-1 text-charcoal">
          <X size={26} aria-hidden="true" />
        </button>
      </div>

      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-4 py-2">
        <ul className="divide-y divide-taupe-200">
          {entries.map((entry) => {
            if (!entry.menu) {
              return (
                <li key={entry.id}>
                  <NavDestination link={entry.link} onClick={close} className={`block py-4 font-serif text-xl ${entry.style === 'cta' ? 'text-burgundy-600' : 'text-charcoal'}`}>
                    {entry.label}
                  </NavDestination>
                </li>
              )
            }
            const isExpanded = expanded === entry.id
            const panelId = `mobile-nav-${entry.id}`
            return (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => setExpanded(isExpanded ? null : entry.id)}
                  aria-expanded={isExpanded}
                  aria-controls={panelId}
                  className="flex w-full items-center justify-between py-4 text-left font-serif text-xl text-charcoal"
                >
                  {entry.label}
                  <ChevronDown size={20} aria-hidden="true" className={`text-charcoal-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </button>
                <div id={panelId} hidden={!isExpanded} className="pb-4">
                  {entry.menu.description && <p className="mb-3 text-sm leading-relaxed text-charcoal-600">{entry.menu.description}</p>}
                  {entry.menu.groups.map((group) => (
                    <div key={group.key} className="mb-3">
                      {group.label && (
                        <p className="mb-1 mt-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-burgundy-600/80">{group.label}</p>
                      )}
                      <ul>
                        {group.links.map((item) => {
                          const Icon = item.icon ? NAV_ICONS[item.icon] : null
                          return (
                            <li key={item.id}>
                              <NavDestination link={item.link} onClick={close} className={subLinkClass}>
                                {Icon && <Icon size={17} aria-hidden="true" className="mt-1 shrink-0 text-burgundy-500" />}
                                <span className="min-w-0">
                                  <span className="block font-semibold">{item.label}</span>
                                  {item.description && <span className="block text-[13px] leading-snug text-charcoal-600">{item.description}</span>}
                                </span>
                              </NavDestination>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  ))}
                  {entry.menu.cta && (
                    <NavDestination link={entry.menu.cta.link} onClick={close} className="inline-flex items-center gap-1.5 pt-1 text-sm font-semibold text-burgundy-600">
                      {entry.menu.cta.label} <ArrowRight size={15} aria-hidden="true" />
                    </NavDestination>
                  )}
                </div>
              </li>
            )
          })}
        </ul>

        <Link to="/newsletter" onClick={close} className="mt-4 flex w-full items-center justify-center bg-plum-600 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-ivory">
          Subscribe
        </Link>

        <ul className="mt-6 space-y-1 border-t border-taupe-200 pt-4">
          {isAuthenticated ? (
            <>
              <li><Link to="/account" onClick={close} className={accountLinkClass}>My account</Link></li>
              <li><Link to="/account/learning" onClick={close} className={accountLinkClass}>My learning</Link></li>
              <li><Link to="/account/saved" onClick={close} className={accountLinkClass}>Saved</Link></li>
              {studioHref && (
                <li>
                  <Link to={studioHref} onClick={close} className="block py-2 text-sm font-semibold text-burgundy-600 hover:text-burgundy-700">
                    WSF Studio
                  </Link>
                </li>
              )}
              <li>
                <button type="button" onClick={signOut} className={`${accountLinkClass} w-full text-left`}>Sign out</button>
              </li>
            </>
          ) : (
            <>
              <li><Link to="/login" onClick={close} className={accountLinkClass}>Sign in</Link></li>
              <li><Link to="/register" onClick={close} className={accountLinkClass}>Create account</Link></li>
            </>
          )}
        </ul>
      </nav>

      {socialLinks.length > 0 && (
        <div className="flex gap-4 border-t border-taupe-200 px-4 py-4">
          {socialLinks.slice(0, 4).map((s) => (
            <a key={s.platform} href={s.url} target="_blank" rel="noreferrer" className="text-xs uppercase tracking-wide text-charcoal-600">
              {s.platform}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
