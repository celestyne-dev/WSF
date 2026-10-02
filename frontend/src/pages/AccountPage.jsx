import { useState } from 'react'
import { Navigate, Link, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { updateProfile } from '../api/auth'
import { logoutUser, setUser } from '../features/auth/authSlice'
import { getRoleLabel } from '../constants/roles'
import useSeo from '../hooks/useSeo'
import CountrySelect from '../components/ui/CountrySelect'
import PageLoader from '../components/ui/PageLoader'

function formFromUser(user) {
  return {
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    displayName: user?.displayName || '',
    bio: user?.bio || '',
    countryCode: user?.countryCode || '',
  }
}

// Mounted only once AccountPage's own guards confirm `user` exists (see
// below), so its initial state can read `user` directly with no
// synchronizing effect. The one time this form's data needs to change out
// from under itself — a successful save — happens inside this
// component's own event handler, which already has the fresh value from
// the response; that's a direct setForm() call, not an effect watching a
// prop (see the "update it from the event that caused the change" guidance
// behind the react(set-state-in-effect) lint rule).
function ProfileForm({ user }) {
  const dispatch = useDispatch()
  const [form, setForm] = useState(() => formFromUser(user))
  const [saving, setSaving] = useState(false)
  const [fieldError, setFieldError] = useState(null)

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function handleSave(e) {
    e.preventDefault()
    setFieldError(null)
    setSaving(true)
    const result = await updateProfile(form)
    setSaving(false)

    if (!result.success) {
      setFieldError(result.message)
      return
    }
    dispatch(setUser(result.user))
    setForm(formFromUser(result.user))
    toast.success('Your profile has been updated.')
  }

  return (
    <form onSubmit={handleSave} className="mt-4 space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="acct-first-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            First name
          </label>
          <input
            id="acct-first-name"
            type="text"
            required
            autoComplete="given-name"
            value={form.firstName}
            onChange={update('firstName')}
            className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="acct-last-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Last name
          </label>
          <input
            id="acct-last-name"
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
        <label htmlFor="acct-display-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
          Display name <span className="font-normal text-charcoal-400">(optional)</span>
        </label>
        <input
          id="acct-display-name"
          type="text"
          autoComplete="nickname"
          value={form.displayName}
          onChange={update('displayName')}
          className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
        />
      </div>
      <div>
        <label htmlFor="acct-bio" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
          Short bio <span className="font-normal text-charcoal-400">(optional)</span>
        </label>
        <textarea
          id="acct-bio"
          rows={3}
          value={form.bio}
          onChange={update('bio')}
          className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
        />
      </div>
      <div>
        <label htmlFor="acct-country" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
          Country <span className="font-normal text-charcoal-400">(optional)</span>
        </label>
        <div className="mt-1.5">
          <CountrySelect
            id="acct-country"
            value={form.countryCode}
            onChange={(v) => setForm((f) => ({ ...f, countryCode: v }))}
          />
        </div>
      </div>

      {fieldError && <p className="text-sm text-burgundy-600">{fieldError}</p>}

      <button type="submit" disabled={saving} className="btn-primary disabled:opacity-60">
        {saving ? 'Saving…' : 'Save changes'}
      </button>
    </form>
  )
}

// /account — a public-layout page (no CMS sidebar) for self-service
// profile editing. Works for any authenticated account, staff included
// (see spec: "do NOT give them any extra admin powers here"); the page
// below never reads or branches on CMS permissions.
export default function AccountPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)
  const countries = useSelector((s) => s.site.countries)
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const [signingOut, setSigningOut] = useState(false)

  // Session restoration itself is centralized in PublicLayout (which wraps
  // every public route, this one included) — dispatching restoreSession()
  // again here too would race it for no benefit, so this page just waits
  // on `user` via the loader guard below.

  useSeo({ title: 'My Account | Women Shaping Futures', robots: 'noindex, nofollow' })

  // Signing out is a deliberate exit, not a session loss: once requested,
  // render a loader instead of the normal guards below, so a lingering
  // render of this page (e.g. while the next route's chunk loads) can't
  // see the now-cleared accessToken and race the "/" we're navigating to
  // with its own redirect to /login.
  if (signingOut) return <PageLoader />
  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />

  const countryName = countries.find((c) => c.code === user.countryCode)?.name

  function handleSignOut() {
    setSigningOut(true)
    dispatch(logoutUser())
    navigate('/', { replace: true })
  }

  return (
    <div className="container-editorial max-w-3xl py-14">
      <p className="eyebrow">My WSF Account</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">{user.name}</h1>

      {/* A. Account overview */}
      <section className="mt-8 border border-taupe-200 p-6">
        <h2 className="font-serif text-xl font-semibold text-charcoal">Overview</h2>
        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Email</dt>
            <dd className="mt-1 text-sm text-charcoal">{user.email}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Account type</dt>
            <dd className="mt-1 text-sm text-charcoal">{getRoleLabel(user.role)}</dd>
          </div>
          {countryName && (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Country</dt>
              <dd className="mt-1 text-sm text-charcoal">{countryName}</dd>
            </div>
          )}
        </dl>
      </section>

      {/* B. Edit profile */}
      <section className="mt-8 border border-taupe-200 p-6">
        <h2 className="font-serif text-xl font-semibold text-charcoal">Edit profile</h2>
        <ProfileForm user={user} />
      </section>

      {/* C. Security */}
      <section className="mt-8 border border-taupe-200 p-6">
        <h2 className="font-serif text-xl font-semibold text-charcoal">Security</h2>
        <p className="mt-2 text-sm text-charcoal-600">Change the password you use to sign in.</p>
        <Link to="/change-password" className="mt-3 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
          Change password
        </Link>
      </section>

      {/* D. Community */}
      <section className="mt-8 border border-taupe-200 p-6">
        <h2 className="font-serif text-xl font-semibold text-charcoal">WSF Community</h2>
        <p className="mt-2 text-sm text-charcoal-600">
          A WSF account and WSF Community membership are separate. Having an account here doesn't automatically make
          you a Community member — joining is a short, separate step whenever you're ready.
        </p>
        <Link to="/community" className="mt-3 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
          Explore the WSF Community
        </Link>
      </section>

      {/* E. Sign out */}
      <section className="mt-8">
        <button
          type="button"
          onClick={handleSignOut}
          className="border border-taupe-300 px-5 py-2.5 text-sm font-semibold text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600"
        >
          Sign out
        </button>
      </section>
    </div>
  )
}
