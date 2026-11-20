import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { User } from 'lucide-react'
import { logoutUser } from '../../features/auth/authSlice'
import { hasCmsAccess, getDefaultCmsRoute } from '../../utils/permissions'

const itemClass = 'block rounded-lg px-3 py-2 text-sm text-charcoal transition-colors hover:bg-cream hover:text-burgundy-600 focus-visible:bg-cream'

// The header's account control: a small disclosure menu (not an ARIA
// `menu`). Signed out: Sign in / Create account. Signed in: account
// shortcuts, WSF Studio for CMS staff only (moved here from the header
// bar so it no longer crowds the public header), and Sign out.
export default function AccountMenu() {
  const user = useSelector((s) => s.auth.user)
  const accessToken = useSelector((s) => s.auth.accessToken)
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const buttonRef = useRef(null)

  // A stored accessToken with `user` still null means restoreSession() is
  // in flight: treated as signed in (no "Sign in" flash). Studio access is
  // only decided once `user` (and its permissions) has loaded.
  const isAuthenticated = Boolean(user || accessToken)
  const studioHref = user && hasCmsAccess(user) ? getDefaultCmsRoute(user) : null

  // Close on route change.
  const [lastPath, setLastPath] = useState(location.pathname)
  if (lastPath !== location.pathname) {
    setLastPath(location.pathname)
    if (open) setOpen(false)
  }

  useEffect(() => {
    if (!open) return undefined
    function onPointerDown(e) {
      if (!rootRef.current?.contains(e.target)) setOpen(false)
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  function signOut() {
    setOpen(false)
    dispatch(logoutUser())
    navigate('/')
  }

  const name = user?.displayName || user?.name || user?.firstName || null

  return (
    <div
      ref={rootRef}
      className="relative"
      onBlur={(e) => {
        if (open && e.relatedTarget && !rootRef.current?.contains(e.relatedTarget)) setOpen(false)
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-controls="account-menu"
        aria-label={isAuthenticated ? 'Account menu' : 'Sign in or create an account'}
        className="rounded-full p-2 text-charcoal transition-colors hover:text-burgundy-600"
      >
        <User size={20} aria-hidden="true" />
      </button>
      <div
        id="account-menu"
        hidden={!open}
        className="absolute right-0 top-full z-50 mt-2 w-60 rounded-2xl border border-taupe-200 bg-white p-2 shadow-[0_24px_48px_-16px_rgba(36,31,33,0.22)]"
      >
        {isAuthenticated ? (
          <>
            {name && <p className="truncate px-3 pb-2 pt-1 text-xs text-charcoal-600">Signed in as <span className="font-semibold text-charcoal">{name}</span></p>}
            <ul>
              <li><Link to="/account" className={itemClass}>My account</Link></li>
              <li><Link to="/account/learning" className={itemClass}>My learning</Link></li>
              <li><Link to="/account/saved" className={itemClass}>Saved</Link></li>
              <li><Link to="/account/membership" className={itemClass}>Membership</Link></li>
              {studioHref && (
                <li className="mt-1 border-t border-taupe-200 pt-1">
                  <Link to={studioHref} className={`${itemClass} font-semibold text-burgundy-600`}>WSF Studio</Link>
                </li>
              )}
              <li className="mt-1 border-t border-taupe-200 pt-1">
                <button type="button" onClick={signOut} className={`${itemClass} w-full text-left`}>Sign out</button>
              </li>
            </ul>
          </>
        ) : (
          <ul>
            <li><Link to="/login" className={itemClass}>Sign in</Link></li>
            <li><Link to="/register" className={itemClass}>Create account</Link></li>
          </ul>
        )}
      </div>
    </div>
  )
}
