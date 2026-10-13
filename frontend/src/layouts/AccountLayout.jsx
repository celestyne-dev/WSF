import { useState } from 'react'
import { Navigate, Outlet, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { logoutUser } from '../features/auth/authSlice'
import { getRoleLabel } from '../constants/roles'
import PageLoader from '../components/ui/PageLoader'
import AccountNavigation from '../components/account/AccountNavigation'

// Shared outer shell for every /account/* page — nested inside PublicLayout
// (normal Header/Footer stay around it), and owns the one auth guard every
// account page used to duplicate: no accessToken -> /login, a token still
// restoring -> PageLoader, a forced password change -> /change-password.
// Individual account pages (routed only as children of this layout) no
// longer need to repeat these checks themselves.
export default function AccountLayout() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)
  const dispatch = useDispatch()
  const navigate = useNavigate()

  // Signing out is a deliberate exit, not a session loss: once requested,
  // render a loader instead of the normal guards below, so a lingering
  // render of this layout (e.g. while the next route's chunk loads) can't
  // see the now-cleared accessToken and race the "/" we're navigating to
  // with its own redirect to /login.
  const [signingOut, setSigningOut] = useState(false)

  if (signingOut) return <PageLoader />
  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />

  function handleSignOut() {
    setSigningOut(true)
    dispatch(logoutUser())
    navigate('/', { replace: true })
  }

  return (
    <div className="container-editorial max-w-[1240px] py-10 lg:py-14">
      <div className="border-b border-taupe-200 pb-6">
        <p className="eyebrow">My WSF Account</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">{user.displayName || user.name}</h1>
        <p className="mt-2 text-sm text-charcoal-600">
          {user.email}
          <span aria-hidden="true"> &middot; </span>
          {getRoleLabel(user.role)}
        </p>
      </div>

      <div className="mt-8 space-y-6 lg:grid lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-16 lg:space-y-0">
        <AccountNavigation onSignOut={handleSignOut} />
        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
