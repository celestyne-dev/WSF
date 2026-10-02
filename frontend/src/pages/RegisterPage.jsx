import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { registerUser } from '../features/auth/authSlice'
import { getPostLoginRoute } from '../utils/permissions'
import useSeo from '../hooks/useSeo'
import CountrySelect from '../components/ui/CountrySelect'

function blankForm() {
  return { firstName: '', lastName: '', email: '', countryCode: '', password: '', confirmPassword: '' }
}

// Creates a WSF account — login + CMS infrastructure (see api/auth.js),
// but deliberately NOT a WSF Community membership: joining /community
// stays its own explicit opt-in (see app/models/community.py), so this
// page never calls that API and never implies "Join Community".
export default function RegisterPage() {
  const [form, setForm] = useState(blankForm())
  const [fieldError, setFieldError] = useState(null)
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const status = useSelector((s) => s.auth.status)

  useSeo({
    title: 'Create Your WSF Account | Women Shaping Futures',
    description: 'Create a free Women Shaping Futures account to save your profile and explore the WSF community.',
    robots: 'noindex, follow',
  })

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFieldError(null)

    if (form.password.length < 8) {
      setFieldError('Your password must be at least 8 characters long.')
      return
    }
    if (form.password !== form.confirmPassword) {
      setFieldError('Password and confirmation do not match.')
      return
    }

    const result = await dispatch(
      registerUser({
        firstName: form.firstName,
        lastName: form.lastName,
        email: form.email,
        password: form.password,
        countryCode: form.countryCode,
      }),
    )

    if (result.meta.requestStatus === 'fulfilled') {
      toast.success(`Welcome to WSF, ${result.payload.user.firstName || 'there'}.`)
      navigate(getPostLoginRoute(result.payload.user))
    } else {
      // result.payload is the normalized { message, errors? } register()
      // returns on failure (see api/auth.js) — errors is the backend's raw
      // field -> [messages] validation map, when there is one.
      const firstFieldError = result.payload?.errors && Object.values(result.payload.errors)[0]?.[0]
      setFieldError(firstFieldError || result.payload?.message || 'Could not create your account.')
    }
  }

  return (
    <div className="container-editorial flex min-h-[70vh] items-center justify-center py-16">
      <div className="w-full max-w-sm">
        <p className="eyebrow text-center">Join WSF</p>
        <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-charcoal">Create your WSF account</h1>
        <p className="mt-3 text-center text-sm text-charcoal-600">
          A WSF account lets you save your profile and manage your settings. It's separate from — and doesn't
          automatically join you to — the WSF Community.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="first-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                First name
              </label>
              <input
                id="first-name"
                type="text"
                required
                autoComplete="given-name"
                value={form.firstName}
                onChange={update('firstName')}
                className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="last-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                Last name
              </label>
              <input
                id="last-name"
                type="text"
                required
                autoComplete="family-name"
                value={form.lastName}
                onChange={update('lastName')}
                className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <label htmlFor="email" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={update('email')}
              className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="country" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Country <span className="font-normal text-charcoal-400">(optional)</span>
            </label>
            <div className="mt-1.5">
              <CountrySelect id="country" value={form.countryCode} onChange={(v) => setForm((f) => ({ ...f, countryCode: v }))} />
            </div>
          </div>
          <div>
            <label htmlFor="password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={update('password')}
              className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
            />
            <p className="mt-1 text-xs text-charcoal-600">At least 8 characters.</p>
          </div>
          <div>
            <label htmlFor="confirm-password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Confirm password
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              autoComplete="new-password"
              value={form.confirmPassword}
              onChange={update('confirmPassword')}
              className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </div>

          {fieldError && <p className="text-sm text-burgundy-600">{fieldError}</p>}

          <button type="submit" disabled={status === 'loading'} className="btn-primary w-full disabled:opacity-60">
            {status === 'loading' ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-charcoal-600">
          By creating an account, you agree to our{' '}
          <Link to="/terms" className="font-semibold text-burgundy-600 hover:underline">
            Terms
          </Link>{' '}
          and{' '}
          <Link to="/privacy" className="font-semibold text-burgundy-600 hover:underline">
            Privacy Policy
          </Link>
          .
        </p>
        <p className="mt-3 text-center text-xs text-charcoal-600">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-burgundy-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
