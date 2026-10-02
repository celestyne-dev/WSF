import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { changePassword } from '../api/auth'
import { restoreSession, setUser } from '../features/auth/authSlice'
import { getDefaultCmsRoute } from '../utils/permissions'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'

// Backs /change-password. Reached two ways: forced, when the authenticated
// user still carries mustChangePassword (a temporary/reset password —
// see AdminLayout's redirect and LoginPage's post-login check), or opened
// directly by an already-settled user as an ordinary change-password
// screen (see routes/AppRoutes.jsx) — the form and submit behavior are
// identical either way; only the copy adapts.
//
// This page sits outside AdminLayout (no sidebar, per spec), so unlike an
// /admin/* route it must restore the session itself: a staff member who
// reaches here with a temporary password and refreshes the browser must
// stay on this page (not bounce to /login or past it) once /auth/me
// confirms mustChangePassword is still true.
export default function ChangePasswordPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)
  const dispatch = useDispatch()
  const navigate = useNavigate()

  useEffect(() => {
    if (accessToken && !user) dispatch(restoreSession())
  }, [accessToken, user, dispatch])

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fieldError, setFieldError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useSeo({ title: 'Change Password | Women Shaping Futures', robots: 'noindex, nofollow' })

  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />

  const forced = !!user.mustChangePassword

  async function handleSubmit(e) {
    e.preventDefault()
    setFieldError(null)

    if (newPassword.length < 8) {
      setFieldError('Your new password must be at least 8 characters long.')
      return
    }
    if (newPassword !== confirmPassword) {
      setFieldError('New password and confirmation do not match.')
      return
    }
    if (newPassword === currentPassword) {
      setFieldError('Your new password must be different from your current password.')
      return
    }

    setSubmitting(true)
    const result = await changePassword({ currentPassword, newPassword, confirmPassword })
    setSubmitting(false)

    if (!result.success) {
      setFieldError(result.message)
      return
    }

    dispatch(setUser(result.user))
    toast.success('Your password has been updated.')
    navigate(getDefaultCmsRoute(result.user))
  }

  return (
    <div className="container-editorial flex min-h-[70vh] items-center justify-center py-16">
      <div className="w-full max-w-sm">
        <p className="eyebrow text-center">{forced ? 'Set your password' : 'Account security'}</p>
        <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">
          {forced ? 'Choose a private password' : 'Change your password'}
        </h1>
        <p className="mt-3 text-center text-sm text-charcoal-600">
          {forced
            ? 'For security, you must set your own password before continuing to the WSF Studio.'
            : 'Update the password you use to sign in to the WSF Studio.'}
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label htmlFor="current-password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Current password
            </label>
            <input
              id="current-password"
              type="password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="new-password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              New password
            </label>
            <input
              id="new-password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
            />
            <p className="mt-1 text-xs text-charcoal-600">At least 8 characters.</p>
          </div>
          <div>
            <label htmlFor="confirm-password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Confirm new password
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </div>

          {fieldError && <p className="text-sm text-burgundy-600">{fieldError}</p>}

          <button type="submit" disabled={submitting} className="btn-primary w-full disabled:opacity-60">
            {submitting ? 'Saving…' : 'Save new password'}
          </button>
        </form>
      </div>
    </div>
  )
}
