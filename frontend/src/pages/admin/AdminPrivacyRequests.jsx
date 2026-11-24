import { useEffect, useId, useState } from 'react'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { createPrivacyRequest, fetchPrivacyRequests, updatePrivacyRequest } from '../../api/accountPrivacy'
import { formatDate } from '../../utils/format'

// Studio -> Privacy requests (permission users.manage). 30 days is WSF's
// operational target, not a claim about any legal deadline.
const TYPES = { access: 'Access / export', correction: 'Correction', deletion: 'Deletion', other: 'Other' }
const STATUSES = { open: 'Open', in_progress: 'In progress', completed: 'Completed', declined: 'Declined / cancelled' }
const field = 'w-full border border-taupe-300 px-3 py-2 text-sm'

function Row({ item, onSaved }) {
  const [status, setStatus] = useState(item.status)
  const [notes, setNotes] = useState(item.adminNotes || '')
  const [message, setMessage] = useState('')
  const id = useId()
  async function save() {
    const res = await updatePrivacyRequest(item.id, { status, adminNotes: notes })
    setMessage(res.success ? 'Saved.' : res.message)
    if (res.success) onSaved(res.item)
  }
  return (
    <li className="space-y-2 border border-taupe-200 bg-white p-4">
      <p className="text-sm">
        <span className="font-semibold">{TYPES[item.requestType]}</span> · {item.requesterName || item.requesterEmail || (item.accountLinked ? 'Member account' : 'Deleted account')}
        {' · '}opened {formatDate(item.openedAt)} · target {formatDate(item.dueAt)}
        {item.overdue && <span className="ml-2 border border-rose-300 px-1.5 text-xs font-semibold text-rose-800">Past the 30-day target</span>}
        {item.source === 'self_service' && <span className="ml-2 text-xs text-charcoal-600">(self-service)</span>}
      </p>
      {item.details && <p className="whitespace-pre-line text-sm text-charcoal-600">{item.details}</p>}
      <div className="grid gap-2 sm:grid-cols-[200px_1fr]">
        <div>
          <label htmlFor={`${id}-s`} className="text-xs font-semibold text-charcoal-600">Status</label>
          <select id={`${id}-s`} value={status} onChange={(e) => setStatus(e.target.value)} className={field}>
            {Object.entries(STATUSES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-n`} className="text-xs font-semibold text-charcoal-600">Internal notes</label>
          <textarea id={`${id}-n`} rows={2} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)} className={field} />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button type="button" onClick={save} className="btn-secondary !px-3 !py-1.5 text-xs">Save</button>
        <span role="status" className="text-xs text-charcoal-600">{message}</span>
        {item.completedAt && <span className="text-xs text-charcoal-600">Closed {formatDate(item.completedAt)}</span>}
      </div>
    </li>
  )
}

export default function AdminPrivacyRequests() {
  const [items, setItems] = useState(undefined)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')
  const [form, setForm] = useState({ requestType: 'access', requesterName: '', requesterEmail: '', details: '' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    fetchPrivacyRequests(filter ? { status: filter } : {}).then((res) => {
      if (!active) return
      if (res.success) setItems(res.items)
      else setError(res.message)
    })
    return () => {
      active = false
    }
  }, [filter, reload])

  async function create(e) {
    e.preventDefault()
    const res = await createPrivacyRequest(form)
    if (res.success) {
      setForm({ requestType: 'access', requesterName: '', requesterEmail: '', details: '' })
      setReload((n) => n + 1)
    } else setError(res.message)
  }

  return (
    <div>
      <AdminPageHeader title="Privacy requests" description="Access, correction, deletion and other requests about personal data. WSF's operational target is 30 days." />
      <details className="mb-5 border border-taupe-200 bg-white p-4">
        <summary className="cursor-pointer text-sm font-semibold">Log a request received by email or phone</summary>
        <form onSubmit={create} className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-charcoal-600">Type
            <select value={form.requestType} onChange={(e) => setForm({ ...form, requestType: e.target.value })} className={field}>
              {Object.entries(TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="text-xs text-charcoal-600">Name
            <input value={form.requesterName} maxLength={200} onChange={(e) => setForm({ ...form, requesterName: e.target.value })} className={field} />
          </label>
          <label className="text-xs text-charcoal-600">Email
            <input type="email" value={form.requesterEmail} maxLength={255} onChange={(e) => setForm({ ...form, requesterEmail: e.target.value })} className={field} />
          </label>
          <label className="text-xs text-charcoal-600 sm:col-span-2">Details
            <textarea rows={2} value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} className={field} />
          </label>
          <button type="submit" className="btn-primary !px-4 !py-2 text-xs sm:col-span-2 sm:w-40">Log request</button>
        </form>
      </details>
      <div className="mb-4">
        <label htmlFor="pr-filter" className="mr-2 text-xs font-semibold text-charcoal-600">Show</label>
        <select id="pr-filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="border border-taupe-300 px-3 py-2 text-sm">
          <option value="">All</option>
          {Object.entries(STATUSES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      {error && <EmptyState title="Couldn't load privacy requests" description={error} />}
      {!error && items === undefined && <PageLoader />}
      {!error && items && (items.length ? (
        <ul className="space-y-3">
          {items.map((item) => <Row key={item.id} item={item} onSaved={() => setReload((n) => n + 1)} />)}
        </ul>
      ) : <EmptyState title="No privacy requests" description="Nothing matches this filter." />)}
    </div>
  )
}
