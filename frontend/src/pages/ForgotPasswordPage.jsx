import { useState } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword } from '../api/auth'
import useSeo from '../hooks/useSeo'

// /forgot-password — carries no secret (unlike /reset-password, see that
// page's own comment), so it stays inside the normal PublicLayout/
// analytics tree like /login and /register.
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // Once true, the form is replaced by a single neutral confirmation —
  // shown identically whether or not the email matched an account (see
  // api/auth.js's forgotPassword(), which never distinguishes the two).
  const [submitted, setSubmitted] = useState(false)

  useSeo({
    title: 'Forgot Password | Women Shaping Futures',
    description: 'Request a password reset link for your Women Shaping Futures account.',
    robots: 'noindex, nofollow',
  })

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    await forgotPassword({ email })
    setSubmitting(false)
    // Always show the same confirmation state, win or lose — never a
    // field error, never "email not found".
    setSubmitted(true)
  }

  return (
    <div className="container-editorial flex min-h-[70vh] items-center justify-center py-16">
      <div className="w-full max-w-sm">
        {submitted ? (
          <>
            <p className="eyebrow text-center">Check your email</p>
            <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">Reset link sent</h1>
            <p className="mt-4 text-center text-sm text-charcoal-600">
              If an account exists for <span className="font-semibold">{email}</span>, we've sent instructions to
              reset your password. The link expires in 30 minutes.
            </p>
            <Link to="/login" className="btn-primary mt-8 block w-full text-center">
              Back to sign in
            </Link>
          </>
        ) : (
          <>
            <p className="eyebrow text-center">Forgot password?</p>
            <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">Reset your password</h1>
            <p className="mt-3 text-center text-sm text-charcoal-600">
              Enter the email address for your WSF account and we'll send you a link to reset your password.
            </p>
            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div>
                <label htmlFor="forgot-email" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Email
                </label>
                <input
                  id="forgot-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>
              <button type="submit" disabled={submitting} className="btn-primary w-full disabled:opacity-60">
                {submitting ? 'Sending…' : 'Send reset link'}
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
