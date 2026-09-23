import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, UserX, UserCheck } from 'lucide-react'
import { fetchSubscriber, updateSubscriber, suppressSubscriber, reactivateSubscriber } from '../../api/newsletter'
import { fetchTopics } from '../../api/taxonomies'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import { formatDate } from '../../utils/format'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

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

export default function AdminSubscriberDetail() {
  const { id } = useParams()

  const [subscriber, setSubscriber] = useState(undefined)
  const [topics, setTopics] = useState([])
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchSubscriber(id), fetchTopics()])
      .then(([sub, topicList]) => {
        if (!active) return
        if (!sub) {
          setNotFound(true)
          return
        }
        setSubscriber(sub)
        setTopics(topicList)
        setForm({ firstName: sub.firstName, lastName: sub.lastName, interestSlugs: sub.interestSlugs })
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this subscriber. Please try again.')
      })
    return () => {
      active = false
    }
  }, [id])

  function toggleInterest(slug) {
    setForm((prev) => ({
      ...prev,
      interestSlugs: prev.interestSlugs.includes(slug) ? prev.interestSlugs.filter((s) => s !== slug) : [...prev.interestSlugs, slug],
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await updateSubscriber(id, form)
      setSubscriber(updated)
      toast.success('Subscriber updated.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong saving this subscriber.')
    } finally {
      setSaving(false)
    }
  }

  async function handleSuppress() {
    try {
      const updated = await suppressSubscriber(id)
      setSubscriber(updated)
      toast.success('Subscriber unsubscribed.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong.')
    } finally {
      setConfirmAction(null)
    }
  }

  async function handleReactivate() {
    try {
      const updated = await reactivateSubscriber(id)
      setSubscriber(updated)
      toast.success('Subscriber reactivated.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong.')
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this subscriber" description={loadError} />
  if (notFound) return <EmptyState title="Subscriber not found" description="This subscriber may have been removed or the URL is incorrect." />
  if (subscriber === undefined || form === null) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={subscriber.email}
        description="Subscriber record — voluntarily supplied details and status only."
        actions={<StatusBadge status={subscriber.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Voluntarily supplied details</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="First name">
                <input value={form.firstName || ''} onChange={(e) => setForm({ ...form, firstName: e.target.value })} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Last name">
                <input value={form.lastName || ''} onChange={(e) => setForm({ ...form, lastName: e.target.value })} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
            <Field label="Interests" hint="optional — used only to target relevant issues, never required">
              <div className="mt-1 flex flex-wrap gap-2">
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
            </Field>
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary mt-4 !px-4 !py-2 text-xs disabled:opacity-60">
              <Save size={13} /> {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Consent &amp; status</p>
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-charcoal-600/70">Signup source</dt>
                <dd className="text-charcoal">{subscriber.source || '—'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Subscribed</dt>
                <dd className="text-charcoal">{subscriber.subscribedAt ? formatDate(subscriber.subscribedAt) : '—'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Unsubscribed</dt>
                <dd className="text-charcoal">{subscriber.unsubscribedAt ? formatDate(subscriber.unsubscribedAt) : '—'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Country</dt>
                <dd className="text-charcoal">{subscriber.country?.name || '—'}</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-charcoal-600/60">
              Consent and subscription timestamps are a factual record and aren't editable here.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Actions</p>
            <div className="mt-3 space-y-2">
              {subscriber.status !== 'unsubscribed' && (
                <button type="button" onClick={() => setConfirmAction('suppress')} className="btn-secondary w-full !py-2 text-xs">
                  <UserX size={13} /> Unsubscribe
                </button>
              )}
              {subscriber.status !== 'active' && (
                <button type="button" onClick={() => setConfirmAction('reactivate')} className="btn-secondary w-full !py-2 text-xs">
                  <UserCheck size={13} /> Reactivate
                </button>
              )}
            </div>
          </div>

          <Link to="/admin/newsletter/subscribers" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all subscribers
          </Link>
        </div>
      </div>

      {confirmAction === 'suppress' && (
        <ConfirmDialog
          title="Unsubscribe this address?"
          description="They will stop receiving newsletter issues. This can be reversed with Reactivate."
          confirmLabel="Unsubscribe"
          danger
          onConfirm={handleSuppress}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction === 'reactivate' && (
        <ConfirmDialog
          title="Reactivate this subscriber?"
          description="They will start receiving newsletter issues again. Only do this if you're sure this address should be active."
          confirmLabel="Reactivate"
          danger={false}
          onConfirm={handleReactivate}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
