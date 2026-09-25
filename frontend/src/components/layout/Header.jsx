import { useEffect, useRef, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { Search, Menu, User } from 'lucide-react'
import Logo from './Logo'
import { toggleMobileNav, toggleSearch } from '../../features/navigation/uiSlice'

function isExternal(url) {
  return !!url && /^https?:\/\//i.test(url)
}

/** A CMS nav item is either a real link (`url` set) or a non-clickable
 * "group" grouping label (`itemType === 'group'`, `url` null) that exists
 * only to hold a dropdown — see backend services/navigation.py. Both can
 * carry children.
 */
function NavTrigger({ item, isOpen, onToggle }) {
  const external = isExternal(item.url)
  const sharedClassName = `flex items-center gap-1 py-7 text-sm font-semibold uppercase tracking-wide text-charcoal transition-colors hover:text-burgundy-600`

  if (!item.url) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-haspopup="true"
        className={sharedClassName}
      >
        {item.label}
      </button>
    )
  }

  if (external) {
    return (
      <a
        href={item.url}
        target={item.openNewTab ? '_blank' : undefined}
        rel={item.openNewTab ? 'noopener noreferrer' : undefined}
        aria-expanded={item.children?.length ? isOpen : undefined}
        aria-haspopup={item.children?.length ? 'true' : undefined}
        className={sharedClassName}
      >
        {item.label}
      </a>
    )
  }

  return (
    <NavLink
      to={item.url}
      aria-expanded={item.children?.length ? isOpen : undefined}
      aria-haspopup={item.children?.length ? 'true' : undefined}
      className={({ isActive }) => `${sharedClassName} ${isActive ? 'text-burgundy-600' : ''}`}
    >
      {item.label}
    </NavLink>
  )
}

export default function Header() {
  const navigation = useSelector((s) => s.site.navigation)
  const dispatch = useDispatch()
  const [openDropdown, setOpenDropdown] = useState(null)
  const navRef = useRef(null)

  const primary = navigation?.primary || []
  const secondary = navigation?.secondary || []

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') setOpenDropdown(null)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Keyboard users tabbing through the header open a dropdown by focusing
  // its trigger or any of its children, and close it once focus leaves
  // the whole <li> — this is the standard "focus-within" pattern, done in
  // JS since it also needs to update `aria-expanded` on the trigger.
  function handleBlur(e, itemId) {
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setOpenDropdown((current) => (current === itemId ? null : current))
    }
  }

  return (
    <header className="sticky top-0 z-40 bg-ivory/95 backdrop-blur">
      {secondary.length > 0 && (
        <div className="hidden border-b border-taupe-200 bg-charcoal text-ivory lg:block">
          <div className="container-editorial flex h-9 items-center justify-end gap-5 text-xs">
            {secondary.map((item) =>
              item.url ? (
                isExternal(item.url) ? (
                  <a
                    key={item.id}
                    href={item.url}
                    target={item.openNewTab ? '_blank' : undefined}
                    rel={item.openNewTab ? 'noopener noreferrer' : undefined}
                    className="tracking-wide hover:text-blush-200"
                  >
                    {item.label}
                  </a>
                ) : (
                  <Link key={item.id} to={item.url} className="tracking-wide hover:text-blush-200">
                    {item.label}
                  </Link>
                )
              ) : null
            )}
          </div>
        </div>
      )}

      <div className="border-b border-taupe-200">
        <div className="container-editorial flex items-center justify-between gap-4 py-3">
          <button
            type="button"
            onClick={() => dispatch(toggleMobileNav(true))}
            aria-label="Open menu"
            className="p-1 text-charcoal lg:hidden"
          >
            <Menu size={26} />
          </button>

          <Logo />

          <nav aria-label="Primary" className="hidden lg:block" ref={navRef}>
            <ul className="flex items-center gap-5 xl:gap-6">
              {primary.map((item) => {
                const hasChildren = item.children?.length > 0
                const isOpen = openDropdown === item.id
                return (
                  <li
                    key={item.id}
                    className="relative"
                    onMouseEnter={() => hasChildren && setOpenDropdown(item.id)}
                    onMouseLeave={() => hasChildren && setOpenDropdown(null)}
                    onFocus={() => hasChildren && setOpenDropdown(item.id)}
                    onBlur={(e) => hasChildren && handleBlur(e, item.id)}
                  >
                    {/* Always opens (never toggles closed) on click — a real
                        mouse click is preceded by a hover, which already
                        opened it via onMouseEnter, so a toggle would
                        immediately close what the hover just opened.
                        Closing happens via mouseleave/blur-out/Escape. */}
                    <NavTrigger item={item} isOpen={isOpen} onToggle={() => setOpenDropdown(item.id)} />
                    {hasChildren && isOpen && (
                      <div
                        role="menu"
                        aria-label={`${item.label} submenu`}
                        className="absolute left-1/2 top-full w-56 -translate-x-1/2 border border-taupe-200 bg-ivory py-2 shadow-card"
                      >
                        {item.children.map((child) =>
                          isExternal(child.url) ? (
                            <a
                              key={child.id}
                              role="menuitem"
                              href={child.url}
                              target={child.openNewTab ? '_blank' : undefined}
                              rel={child.openNewTab ? 'noopener noreferrer' : undefined}
                              className="block px-4 py-2 text-sm text-charcoal-600 hover:bg-blush-50 hover:text-burgundy-600"
                            >
                              {child.label}
                            </a>
                          ) : (
                            <Link
                              key={child.id}
                              role="menuitem"
                              to={child.url}
                              className="block px-4 py-2 text-sm text-charcoal-600 hover:bg-blush-50 hover:text-burgundy-600"
                            >
                              {child.label}
                            </Link>
                          )
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </nav>

          <div className="flex items-center gap-1 sm:gap-2">
            <button
              type="button"
              onClick={() => dispatch(toggleSearch(true))}
              aria-label="Search"
              className="p-2 text-charcoal transition-colors hover:text-burgundy-600"
            >
              <Search size={20} />
            </button>
            <Link to="/login" aria-label="Account" className="hidden p-2 text-charcoal transition-colors hover:text-burgundy-600 sm:block">
              <User size={20} />
            </Link>
            <Link to="/newsletter" className="ml-1 hidden bg-plum-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ivory transition-colors hover:bg-plum-700 md:inline-flex">
              Subscribe
            </Link>
          </div>
        </div>
      </div>
    </header>
  )
}
