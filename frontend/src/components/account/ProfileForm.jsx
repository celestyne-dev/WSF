import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { toast } from 'react-toastify'
import { updateProfile } from '../../api/auth'
import { setUser } from '../../features/auth/authSlice'
import CountrySelect from '../ui/CountrySelect'

function formFromUser(user) {
  return {
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    displayName: user?.displayName || '',
    bio: user?.bio || '',
    countryCode: user?.countryCode || '',
  }
}

// Mounted only once a caller's own guards confirm `user` exists, so its
// initial state can read `user` directly with no synchronizing effect. The
// one time this form's data needs to change out from under itself — a
// successful save — happens inside this component's own event handler,
// which already has the fresh value from the response; that's a direct
// setForm() call, not an effect watching a prop (see the "update it from
// the event that caused the change" guidance behind the
// react(set-state-in-effect) lint rule).
export default function ProfileForm({ user }) {
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
