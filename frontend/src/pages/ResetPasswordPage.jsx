import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { resetPassword } from '../api/auth'

// /reset-password — deliberately rendered OUTSIDE PublicLayout (see
// routes/AppRoutes.jsx) and imports nothing from it: no Header/Footer/
// MobileNav/SearchOverlay, no useSiteStructuredData, no
// captureAcquisitionContext. The raw reset token arrives in the URL
// fragment (#token=...), which PublicLayout's route-change effect would
// otherwise run analytics/acquisition-tracking code against on every
// navigation — this page exists specifically so that never happens. The
// token lives only in this component's own state for exactly as long as
// it takes to submit the reset request: never Redux, never
// localStorage/sessionStorage, never passed to any analytics call, and
// stripped from the visible URL immediately after being read.
// Read once, synchronously, at first render — not from an effect, so
// capturing it never triggers a second render purely to hold a value
// that's already known by the time this component first paints. The one
// genuine side effect (clearing the token from the visible URL) still
// belongs in an effect below, since render itself must stay pure.
function readTokenFromLocationHash() {
  if (typeof window === 'undefined') return null
  const match = (window.location.hash || '').match(/token=([^&]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export default function ResetPasswordPage() {
  const [token, setToken] = useState(readTokenFromLocationHash)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [fieldError, setFieldError] = useState(null)
  const [succeeded, setSucceeded] = useState(false)

  useEffect(() => {
    document.title = 'Reset Password | Women Shaping Futures'

    // Remove the token from the visible URL immediately — it was
    // already captured into this component's own state above, so
    // nothing downstream (browser history, a shared/bookmarked link, a
    // screen-reader announcing the address bar) keeps carrying it.
    if (window.location.hash) {
      history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setFieldError(null)

    if (newPassword.length < 8) {
      setFieldError('Your new password must be at least 8 characters long.')
      return
    }
    if (newPassword !== confirmPassword) {
      setFieldError('Password and confirmation do not match.')
      return
    }

    setSubmitting(true)
    const result = await resetPassword({ token, newPassword, confirmPassword })
    setSubmitting(false)

    if (!result.success) {
      setFieldError(result.message)
      return
    }

    // Clear every trace of the token/password from memory now that the
    // request is done, win or lose from here on is moot — succeeded.
    setToken(null)
    setNewPassword('')
    setConfirmPassword('')
    setSucceeded(true)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-ivory px-4 py-16">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-8 flex justify-center font-serif text-xl font-semibold text-charcoal">
          Women Shaping <span className="text-burgundy-500">Futures</span>
        </Link>

        {succeeded ? (
          <>
            <p className="eyebrow text-center">Password updated</p>
            <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">You're all set</h1>
            <p className="mt-4 text-center text-sm text-charcoal-600">
              Your password has been reset. You may now sign in with your new password.
            </p>
            <Link to="/login" className="btn-primary mt-8 block w-full text-center">
              Sign in
            </Link>
          </>
        ) : token === null ? (
          <>
            <p className="eyebrow text-center">Invalid link</p>
            <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">Reset link problem</h1>
            <p className="mt-4 text-center text-sm text-charcoal-600">
              This password reset link is invalid or incomplete.
            </p>
            <Link to="/forgot-password" className="btn-primary mt-8 block w-full text-center">
              Request a new link
            </Link>
          </>
        ) : (
          <>
            <p className="eyebrow text-center">Reset your password</p>
            <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">Choose a new password</h1>
            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
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
                <label htmlFor="confirm-new-password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Confirm new password
                </label>
                <input
                  id="confirm-new-password"
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
                {submitting ? 'Resetting…' : 'Reset password'}
              </button>
            </form>
            <p className="mt-6 text-center text-xs text-charcoal-600">
              <Link to="/login" className="font-semibold text-burgundy-600 hover:underline">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
