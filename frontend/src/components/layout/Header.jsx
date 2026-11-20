import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { ChevronDown, Menu, Search } from 'lucide-react'
import Logo from './Logo'
import AccountMenu from './AccountMenu'
import MegaMenuPanel from './MegaMenuPanel'
import NavDestination from './NavDestination'
import { toggleMobileNav, toggleSearch } from '../../features/navigation/uiSlice'
import { buildHeaderNavigation, isEntryActive } from '../../utils/megaMenu'

// Short grace period before a hover-opened menu closes, so moving the
// pointer from a trigger down into its panel (or across a small gap)
// never closes it by accident.
const CLOSE_DELAY_MS = 150

// Header height is fixed (64px, 68px from lg, plus a 1px border) so the
// server's first-paint placeholder (backend spa_shell._HEADER_PLACEHOLDER_OPEN
// and _HEADER_RESERVE_STYLE) reserves exactly this space and the page does
// not move when React mounts. Keep those heights in sync with this file.
//
// The desktop bar starts at `xl` (1280px): measured in Chromium, six
// top-level items plus the wordmark and actions need ~1,200px, so at `lg`
// (1024px) they overflowed. Below xl the accordion menu is used.
const triggerBase =
  'relative inline-flex h-full items-center gap-1 whitespace-nowrap px-3 text-[15px] font-semibold text-charcoal transition-colors hover:text-burgundy-600 focus-visible:text-burgundy-600 2xl:px-4'
const activeBar = 'after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-burgundy-600 2xl:after:inset-x-4'

export default function Header() {
  const navigation = useSelector((s) => s.site.navigation)
  const dispatch = useDispatch()
  const location = useLocation()
  const entries = useMemo(() => buildHeaderNavigation(navigation), [navigation])

  // { id, reason: 'hover' | 'click' } — only one menu is ever open. A
  // hover-opened menu closes when the pointer leaves trigger + panel; a
  // click/keyboard-opened one stays until clicked again, Escape, an
  // outside click, or navigation.
  const [open, setOpen] = useState(null)
  const closeTimer = useRef(null)
  const headerRef = useRef(null)
  const triggerRefs = useRef({})

  // The server's static first-paint header placeholder (outside #root) is
  // replaced by this header before the browser paints React's first frame.
  useLayoutEffect(() => {
    document.querySelectorAll('[data-wsf-header-placeholder], [data-wsf-header-placeholder-style]').forEach((el) => el.remove())
  }, [])

  const cancelClose = useCallback(() => {
    clearTimeout(closeTimer.current)
  }, [])

  const close = useCallback(() => {
    clearTimeout(closeTimer.current)
    setOpen(null)
  }, [])

  const openMenu = useCallback((id, reason) => {
    clearTimeout(closeTimer.current)
    setOpen((current) => (current?.id === id && current.reason === 'click' && reason === 'hover' ? current : { id, reason }))
  }, [])

  const scheduleClose = useCallback(() => {
    clearTimeout(closeTimer.current)
    closeTimer.current = setTimeout(() => setOpen((current) => (current?.reason === 'hover' ? null : current)), CLOSE_DELAY_MS)
  }, [])

  // Navigating closes any open menu.
  const [lastPath, setLastPath] = useState(location.pathname)
  if (lastPath !== location.pathname) {
    setLastPath(location.pathname)
    if (open) setOpen(null)
  }

  useEffect(() => () => clearTimeout(closeTimer.current), [])

  useEffect(() => {
    if (!open) return undefined
    function onKeyDown(e) {
      if (e.key === 'Escape') {
        const trigger = triggerRefs.current[open.id]
        close()
        trigger?.focus()
      }
    }
    function onPointerDown(e) {
      if (!headerRef.current?.contains(e.target)) close()
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [open, close])

  function onTriggerClick(id) {
    setOpen((current) => (current?.id === id && current.reason === 'click' ? null : { id, reason: 'click' }))
  }

  function onTriggerKeyDown(e, id) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      openMenu(id, 'click')
      requestAnimationFrame(() => document.getElementById(`mega-menu-${id}`)?.querySelector('a')?.focus())
    }
  }

  // Mouse only: touch "hover" must not open-then-close on tap.
  const onHoverEnter = (id) => (e) => {
    if (e.pointerType === 'mouse') openMenu(id, 'hover')
  }
  const onHoverLeave = (e) => {
    if (e.pointerType === 'mouse') scheduleClose()
  }

  const menuEntries = entries.filter((e) => e.menu)
  const isMenuOpen = Boolean(open)

  return (
    <header
      ref={headerRef}
      className={`sticky top-0 z-40 border-b border-taupe-200 bg-ivory transition-shadow ${isMenuOpen ? 'shadow-sm' : ''}`}
      onBlur={(e) => {
        // Keyboard focus leaving the header closes an open menu.
        if (open && e.relatedTarget && !headerRef.current?.contains(e.relatedTarget)) close()
      }}
    >
      <div className="container-editorial flex h-16 items-center gap-4 lg:h-[68px]">
        <div className="mr-auto shrink-0 xl:mr-4 2xl:mr-10">
          <Logo />
        </div>

        <nav aria-label="Primary" className="hidden h-full flex-1 justify-center xl:flex">
          <ul className="flex h-full items-stretch">
            {entries.map((entry) => {
              const active = isEntryActive(entry, location.pathname)
              const cta = entry.style === 'cta'
              const className = `${triggerBase} ${active ? `text-burgundy-600 ${activeBar}` : ''} ${cta ? 'text-burgundy-600' : ''}`
              if (!entry.menu) {
                return (
                  <li key={entry.id} className="flex h-full">
                    <NavDestination link={entry.link} className={className} aria-current={active ? 'page' : undefined}>
                      {entry.label}
                    </NavDestination>
                  </li>
                )
              }
              const isOpen = open?.id === entry.id
              return (
                <li key={entry.id} className="flex h-full" onPointerEnter={onHoverEnter(entry.id)} onPointerLeave={onHoverLeave}>
                  <button
                    ref={(el) => {
                      triggerRefs.current[entry.id] = el
                    }}
                    type="button"
                    aria-expanded={isOpen}
                    aria-haspopup="true"
                    aria-controls={`mega-menu-${entry.id}`}
                    onClick={() => onTriggerClick(entry.id)}
                    onKeyDown={(e) => onTriggerKeyDown(e, entry.id)}
                    className={`${className} ${isOpen ? 'text-burgundy-600' : ''}`}
                  >
                    {entry.label}
                    <ChevronDown size={14} aria-hidden="true" className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>

        <div className="flex items-center gap-1 xl:ml-4 2xl:ml-6">
          <button
            type="button"
            onClick={() => dispatch(toggleSearch(true))}
            aria-label="Search"
            className="rounded-full p-2 text-charcoal transition-colors hover:text-burgundy-600"
          >
            <Search size={20} aria-hidden="true" />
          </button>
          <div className="hidden sm:block">
            <AccountMenu />
          </div>
          <Link
            to="/newsletter"
            className="ml-2 hidden bg-plum-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ivory transition-colors hover:bg-plum-700 md:inline-flex"
          >
            Subscribe
          </Link>
          <button
            type="button"
            onClick={() => dispatch(toggleMobileNav(true))}
            aria-label="Open menu"
            className="ml-1 p-1 text-charcoal xl:hidden"
          >
            <Menu size={26} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="hidden xl:block">
        {menuEntries.map((entry) => (
          <MegaMenuPanel
            key={entry.id}
            id={`mega-menu-${entry.id}`}
            entry={entry}
            open={open?.id === entry.id}
            onNavigate={close}
            onPointerEnter={(e) => {
              if (e.pointerType === 'mouse') cancelClose()
            }}
            onPointerLeave={onHoverLeave}
          />
        ))}
      </div>
    </header>
  )
}
