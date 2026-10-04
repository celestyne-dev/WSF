import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save } from 'lucide-react'
import {
  fetchAdminCirclePlans,
  fetchCircleSubscription,
  createCircleSubscription,
  updateCircleSubscription,
} from '../../api/circle'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const SOURCES = ['external', 'manual', 'complimentary']
const ALL_STATUSES = ['pending', 'active', 'past_due', 'cancelled', 'expired', 'revoked']

// Mirrors app/services/circle.py's explicit allowed-transition map — the
// frontend only ever offers transitions the backend will actually accept,
// so a staff member never hits a surprise 422 after filling out the form.
const ALLOWED_TRANSITIONS = {
  pending: ['pending', 'active', 'cancelled', 'revoked'],
  active: ['active', 'past_due', 'cancelled', 'expired', 'revoked'],
  past_due: ['past_due', 'active', 'cancelled', 'expired', 'revoked'],
  cancelled: ['cancelled'],
  expired: ['expired'],
  revoked: ['revoked'],
}

function toDateTimeLocal(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fromDateTimeLocal(value) {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

function blankNewForm() {
  return {
    email: '',
    planId: '',
    status: 'pending',
    source: 'manual',
    provider: '',
    providerCustomerId: '',
    providerSubscriptionId: '',
    paymentReference: '',
    startsAt: '',
    currentPeriodStart: '',
    currentPeriodEnd: '',
    cancelAtPeriodEnd: false,
  }
}

function toExistingForm(sub) {
  return {
    status: sub.status,
    provider: sub.provider || '',
    providerCustomerId: sub.providerCustomerId || '',
    providerSubscriptionId: sub.providerSubscriptionId || '',
    paymentReference: sub.paymentReference || '',
    startsAt: toDateTimeLocal(sub.startsAt),
    currentPeriodStart: toDateTimeLocal(sub.currentPeriodStart),
    currentPeriodEnd: toDateTimeLocal(sub.currentPeriodEnd),
    cancelAtPeriodEnd: !!sub.cancelAtPeriodEnd,
  }
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
        {label} {hint && <span className="normal-case text-charcoal-600/60">— {hint}</span>}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

export default function AdminCircleMembershipDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [plans, setPlans] = useState([])
  const [subscription, setSubscription] = useState(undefined)
  const [form, setForm] = useState(isNew ? blankNewForm() : undefined)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    fetchAdminCirclePlans().then((list) => active && setPlans(list)).catch(() => {})
    if (!isNew) {
      fetchCircleSubscription(id)
        .then((sub) => {
          if (!active) return
          if (sub) {
            setSubscription(sub)
            setForm(toExistingForm(sub))
          } else {
            setNotFound(true)
          }
        })
        .catch(() => active && setLoadError('Something went wrong loading this membership. Please try again.'))
    }
    return () => {
      active = false
    }
  }, [id, isNew])

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleCreate() {
    if (!form.email.trim()) {
      toast.error('Enter the account email.')
      return
    }
    if (!form.planId) {
      toast.error('Select a plan.')
      return
    }
    setSaving(true)
    try {
      const payload = {
        email: form.email.trim(),
        planId: Number(form.planId),
        status: form.status,
        source: form.source,
        provider: form.provider || undefined,
        providerCustomerId: form.providerCustomerId || undefined,
        providerSubscriptionId: form.providerSubscriptionId || undefined,
        paymentReference: form.paymentReference || undefined,
        startsAt: fromDateTimeLocal(form.startsAt) || undefined,
        currentPeriodStart: fromDateTimeLocal(form.currentPeriodStart) || undefined,
        currentPeriodEnd: fromDateTimeLocal(form.currentPeriodEnd) || undefined,
        cancelAtPeriodEnd: form.cancelAtPeriodEnd,
      }
      const created = await createCircleSubscription(payload)
      toast.success('Membership recorded.')
      navigate(`/admin/circle/memberships/${created.id}`)
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong recording this membership.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const payload = {
        status: form.status,
        provider: form.provider || null,
        providerCustomerId: form.providerCustomerId || null,
        providerSubscriptionId: form.providerSubscriptionId || null,
        paymentReference: form.paymentReference || null,
        startsAt: fromDateTimeLocal(form.startsAt),
        currentPeriodStart: fromDateTimeLocal(form.currentPeriodStart),
        currentPeriodEnd: fromDateTimeLocal(form.currentPeriodEnd),
        cancelAtPeriodEnd: form.cancelAtPeriodEnd,
      }
      const updated = await updateCircleSubscription(id, payload)
      setSubscription(updated)
      setForm(toExistingForm(updated))
      toast.success('Membership updated.')
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong updating this membership.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this membership" description={loadError} />
  if (notFound) return <EmptyState title="Membership not found" description="This record may have been removed or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  if (isNew) {
    return (
      <div>
        <AdminPageHeader
          title="Record WSF Circle membership"
          description="For an EXISTING WSF account only — found by exact email. This never creates a new account."
        />
        <div className="max-w-xl space-y-6">
          <div className="border border-taupe-200 bg-white p-6 space-y-4">
            <Field label="Account email" hint="must exactly match an existing WSF account">
              <input type="email" value={form.email} onChange={(e) => update('email', e.target.value)} className={inputClass} />
            </Field>
            <Field label="Plan">
              <select value={form.planId} onChange={(e) => update('planId', e.target.value)} className={inputClass}>
                <option value="">Select a plan…</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.status})
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Initial status">
                <select value={form.status} onChange={(e) => update('status', e.target.value)} className={inputClass}>
                  {ALL_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Source" hint="how this membership came about">
                <select value={form.source} onChange={(e) => update('source', e.target.value)} className={inputClass}>
                  {SOURCES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Period &amp; reference (optional)</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Starts at">
                <input type="datetime-local" value={form.startsAt} onChange={(e) => update('startsAt', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Current period end">
                <input type="datetime-local" value={form.currentPeriodEnd} onChange={(e) => update('currentPeriodEnd', e.target.value)} className={inputClass} />
              </Field>
            </div>
            <Field label="Provider" hint="e.g. a future payment provider name — optional reference only">
              <input value={form.provider} onChange={(e) => update('provider', e.target.value)} className={inputClass} />
            </Field>
            <Field label="Payment reference" hint="optional — e.g. a bank transfer or invoice reference">
              <input value={form.paymentReference} onChange={(e) => update('paymentReference', e.target.value)} className={inputClass} />
            </Field>
          </div>

          <button type="button" onClick={handleCreate} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
            <Save size={13} /> {saving ? 'Recording…' : 'Record membership'}
          </button>
        </div>
      </div>
    )
  }

  const allowedNext = ALLOWED_TRANSITIONS[subscription.status] || [subscription.status]

  return (
    <div>
      <AdminPageHeader
        title={`Membership #${subscription.id}`}
        description={`${subscription.user?.fullName || 'Unknown'} — ${subscription.user?.email || ''}`}
        actions={<StatusBadge status={subscription.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Plan</p>
            <p className="text-sm text-charcoal">{subscription.plan?.name || '—'}</p>
            <p className="text-xs text-charcoal-600/70">
              {subscription.plan?.billingInterval} &middot; {subscription.source}
            </p>
          </div>

          <div className="border border-taupe-200 bg-white p-6 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Status</p>
            <select value={form.status} onChange={(e) => update('status', e.target.value)} className={inputClass}>
              {allowedNext.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.cancelAtPeriodEnd} onChange={(e) => update('cancelAtPeriodEnd', e.target.checked)} />
              Cancel at period end
            </label>
          </div>

          <div className="border border-taupe-200 bg-white p-6 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Period</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Starts at">
                <input type="datetime-local" value={form.startsAt} onChange={(e) => update('startsAt', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Current period start">
                <input type="datetime-local" value={form.currentPeriodStart} onChange={(e) => update('currentPeriodStart', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Current period end">
                <input type="datetime-local" value={form.currentPeriodEnd} onChange={(e) => update('currentPeriodEnd', e.target.value)} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Provider / reference metadata</p>
            <p className="text-xs text-charcoal-600/60">Staff-only — never shown to the member or publicly.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Provider">
                <input value={form.provider} onChange={(e) => update('provider', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Payment reference">
                <input value={form.paymentReference} onChange={(e) => update('paymentReference', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Provider customer ID">
                <input value={form.providerCustomerId} onChange={(e) => update('providerCustomerId', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Provider subscription ID">
                <input value={form.providerSubscriptionId} onChange={(e) => update('providerSubscriptionId', e.target.value)} className={inputClass} />
              </Field>
            </div>
          </div>

          <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
            <Save size={13} /> {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">History</p>
            <dl className="mt-3 space-y-2 text-sm">
              <div>
                <dt className="text-charcoal-600/70">Created</dt>
                <dd className="text-charcoal">{subscription.createdAt ? formatDate(subscription.createdAt) : '—'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Cancelled</dt>
                <dd className="text-charcoal">{subscription.cancelledAt ? formatDate(subscription.cancelledAt) : '—'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Ended</dt>
                <dd className="text-charcoal">{subscription.endedAt ? formatDate(subscription.endedAt) : '—'}</dd>
              </div>
            </dl>
          </div>

          <Link to="/admin/circle/memberships" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all memberships
          </Link>
        </div>
      </div>
    </div>
  )
}
