import { useEffect, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import {
  fetchMyCommunityMembership,
  updateMyCommunityProfile,
  leaveCommunity,
  rejoinCommunity,
} from '../api/community'
import { fetchTopics } from '../api/taxonomies'
import CountrySelect from '../components/ui/CountrySelect'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import { formatDate } from '../utils/format'

// Staff-controlled states a self-service member can land in without being
// able to reactivate herself — see backend
// app/services/community_accounts.py::rejoin_community's
// _REACTIVATABLE_STATUSES. Friendly copy only; never the raw status label
// or any internal moderation reason (spec: "Do not surface internal admin
// notes").
const SAFE_STATE_COPY = {
  pending: 'Your Community application is currently being reviewed by our team.',
  paused: "Your Community membership is currently paused. If you have questions, please contact Women Shaping Futures.",
  declined: "Your Community membership isn't currently active. If you have questions, please contact Women Shaping Futures.",
  archived: "Your Community membership isn't currently active. If you have questions, please contact Women Shaping Futures.",
}

function formFromMember(member) {
  return {
    firstName: member?.firstName || '',
    lastName: member?.lastName || '',
    professionalTitle: member?.professionalTitle || '',
    organizationName: member?.organizationName || '',
    shortBio: member?.shortBio || '',
    websiteUrl: member?.websiteUrl || '',
    linkedinUrl: member?.linkedinUrl || '',
    countryCode: member?.countryCode || '',
    city: member?.city || '',
    interestSlugs: member?.interestSlugs || [],
    communityUpdatesOptIn: !!member?.communityUpdatesOptIn,
    directoryOptIn: !!member?.directoryOptIn,
  }
}

function ProfileForm({ member, topics, onSaved }) {
  const [form, setForm] = useState(() => formFromMember(member))
  const [saving, setSaving] = useState(false)

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  function toggleInterest(slug) {
    setForm((f) => ({
      ...f,
      interestSlugs: f.interestSlugs.includes(slug) ? f.interestSlugs.filter((s) => s !== slug) : [...f.interestSlugs, slug],
    }))
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await updateMyCommunityProfile(form)
      onSaved(updated)
      toast.success('Your Community profile has been updated.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSave} className="mt-4 space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="cm-first-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">First name</label>
          <input id="cm-first-name" required value={form.firstName} onChange={update('firstName')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
        <div>
          <label htmlFor="cm-last-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Last name</label>
          <input id="cm-last-name" required value={form.lastName} onChange={update('lastName')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="cm-title" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Professional title <span className="font-normal text-charcoal-400">(optional)</span></label>
          <input id="cm-title" value={form.professionalTitle} onChange={update('professionalTitle')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
        <div>
          <label htmlFor="cm-org" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Organization <span className="font-normal text-charcoal-400">(optional)</span></label>
          <input id="cm-org" value={form.organizationName} onChange={update('organizationName')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
      </div>
      <div>
        <label htmlFor="cm-bio" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Short bio <span className="font-normal text-charcoal-400">(optional)</span></label>
        <textarea id="cm-bio" rows={3} value={form.shortBio} onChange={update('shortBio')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="cm-website" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Website <span className="font-normal text-charcoal-400">(optional)</span></label>
          <input id="cm-website" type="url" value={form.websiteUrl} onChange={update('websiteUrl')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
        <div>
          <label htmlFor="cm-linkedin" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">LinkedIn <span className="font-normal text-charcoal-400">(optional)</span></label>
          <input id="cm-linkedin" type="url" value={form.linkedinUrl} onChange={update('linkedinUrl')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="cm-country" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Country</label>
          <div className="mt-1.5">
            <CountrySelect id="cm-country" value={form.countryCode} onChange={(v) => setForm((f) => ({ ...f, countryCode: v }))} />
          </div>
        </div>
        <div>
          <label htmlFor="cm-city" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">City <span className="font-normal text-charcoal-400">(optional)</span></label>
          <input id="cm-city" value={form.city} onChange={update('city')} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
      </div>

      {topics.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Interests</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {topics.map((t) => (
              <button
                key={t.slug}
                type="button"
                onClick={() => toggleInterest(t.slug)}
                className={`px-2.5 py-1 text-xs font-medium ${form.interestSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
              >
                {t.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <label className="flex items-start gap-2 text-sm text-charcoal-600">
        <input type="checkbox" checked={form.communityUpdatesOptIn} onChange={(e) => setForm((f) => ({ ...f, communityUpdatesOptIn: e.target.checked }))} className="mt-0.5" />
        Send me Community updates (e.g. news about my membership)
      </label>

      <label className="flex items-start gap-2 text-sm text-charcoal-600">
        <input type="checkbox" checked={form.directoryOptIn} onChange={(e) => setForm((f) => ({ ...f, directoryOptIn: e.target.checked }))} className="mt-0.5" />
        Show my Community profile in the public member directory
      </label>

      {form.directoryOptIn ? (
        <p className="text-sm font-semibold text-emerald-700">Your Community profile is visible in the member directory.</p>
      ) : (
        <p className="text-sm text-charcoal-600/70">Your Community profile is not visible in the public directory.</p>
      )}

      <button type="submit" disabled={saving} className="btn-primary disabled:opacity-60">
        {saving ? 'Saving…' : 'Save changes'}
      </button>
    </form>
  )
}

export default function AccountCommunityPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)

  const [membership, setMembership] = useState(undefined)
  const [topics, setTopics] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  useSeo({ title: 'My Community | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    if (!accessToken) return undefined
    let cancelled = false
    fetchMyCommunityMembership()
      .then((result) => {
        if (!cancelled) {
          setMembership(result)
          setError(null)
        }
      })
      .catch(() => {
        if (!cancelled) setError("We couldn't load your Community membership. Please try again.")
      })
    fetchTopics().then((list) => !cancelled && setTopics(list)).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [accessToken, retryCount])

  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />

  async function handleLeave() {
    if (!window.confirm('Leave the WSF Community? Your account and other WSF features are not affected.')) return
    setBusy(true)
    try {
      const updated = await leaveCommunity()
      setMembership({ joined: true, member: updated })
      toast.success("You've left the WSF Community.")
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function handleRejoin() {
    setBusy(true)
    try {
      const updated = await rejoinCommunity()
      setMembership({ joined: true, member: updated })
      toast.success('Welcome back to the WSF Community!')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || "This membership can't be reactivated automatically.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container-editorial max-w-3xl py-14">
      <p className="eyebrow">My WSF Account</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">My Community</h1>

      <div className="mt-8">
        {error ? (
          <div className="border border-taupe-200 p-6">
            <p className="text-sm text-charcoal-600">{error}</p>
            <button type="button" onClick={() => setRetryCount((n) => n + 1)} className="btn-secondary mt-4">
              Try again
            </button>
          </div>
        ) : membership === undefined ? (
          <div className="h-40 animate-pulse bg-taupe-100" />
        ) : !membership.joined ? (
          <div className="border border-taupe-200 p-6">
            <p className="text-sm text-charcoal-600">
              Your WSF account and the WSF Community are separate. Having an account here doesn't automatically make
              you a Community member — joining is a short, separate step whenever you're ready.
            </p>
            <Link to="/community#join" className="btn-primary mt-4 inline-block">
              Join the WSF Community
            </Link>
          </div>
        ) : membership.member.status === 'active' ? (
          <div className="border border-taupe-200 p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{membership.member.membershipType}</p>
                {membership.member.activatedAt && (
                  <p className="mt-1 text-sm text-charcoal-600">Member since {formatDate(membership.member.activatedAt)}</p>
                )}
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={handleLeave}
                className="text-sm font-semibold text-charcoal-600 hover:text-burgundy-600 disabled:opacity-60"
              >
                Leave Community
              </button>
            </div>
            <ProfileForm
              member={membership.member}
              topics={topics}
              onSaved={(updated) => setMembership({ joined: true, member: updated })}
            />
          </div>
        ) : ['left', 'inactive'].includes(membership.member.status) ? (
          <div className="border border-taupe-200 p-6">
            <p className="text-sm text-charcoal-600">You're not currently an active member of the WSF Community.</p>
            <button type="button" disabled={busy} onClick={handleRejoin} className="btn-primary mt-4 disabled:opacity-60">
              {busy ? 'Rejoining…' : 'Rejoin the Community'}
            </button>
          </div>
        ) : (
          <div className="border border-taupe-200 p-6">
            <p className="text-sm text-charcoal-600">
              {SAFE_STATE_COPY[membership.member.status] || "Your Community membership isn't currently active."}
            </p>
            <Link to="/contact" className="mt-3 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
              Contact Women Shaping Futures
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
