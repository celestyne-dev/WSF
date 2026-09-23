import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Archive, Link2, Unlink, UserPlus, MessageSquarePlus } from 'lucide-react'
import {
  fetchPartnership,
  updatePartnership,
  updatePartnershipStatus,
  assignPartnership,
  linkPartnershipOrganization,
  addPartnershipNote,
  archivePartnership,
  fetchPartnershipHistory,
} from '../../api/partnerships'
import { fetchAdminUsers } from '../../api/admin'
import { fetchOrganizations } from '../../api/taxonomies'
import { fetchCountries } from '../../api/geography'
import { PARTNERSHIP_TYPES, PARTNERSHIP_STATUSES } from '../../constants/partnerships'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import { formatDate } from '../../utils/format'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const DANGER_STATUSES = new Set(['declined', 'archived'])

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

function toForm(p) {
  return {
    contactName: p.contactName || '',
    email: p.email || '',
    phone: p.phone || '',
    jobTitle: p.jobTitle || '',
    company: p.company || '',
    website: p.website || '',
    countryCode: p.countryCode || '',
    partnershipType: p.partnershipType || '',
    subject: p.subject || '',
    message: p.message || '',
    goals: p.goals || '',
    proposedTiming: p.proposedTiming || '',
    budgetRange: p.budgetRange || '',
    estimatedValue: p.estimatedValue ?? '',
    currency: p.currency || '',
    commercialNotes: p.commercialNotes || '',
    proposedStartDate: p.proposedStartDate || '',
    proposedEndDate: p.proposedEndDate || '',
    actualStartDate: p.actualStartDate || '',
    actualEndDate: p.actualEndDate || '',
  }
}

export default function AdminPartnershipDetail() {
  const { id } = useParams()

  const [partnership, setPartnership] = useState(undefined)
  const [form, setForm] = useState(null)
  const [users, setUsers] = useState([])
  const [organizations, setOrganizations] = useState([])
  const [countries, setCountries] = useState([])
  const [history, setHistory] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  const [saving, setSaving] = useState(false)
  const [statusValue, setStatusValue] = useState('')
  const [savingStatus, setSavingStatus] = useState(false)
  const [assigneeId, setAssigneeId] = useState('')
  const [savingAssignee, setSavingAssignee] = useState(false)
  const [orgSlug, setOrgSlug] = useState('')
  const [savingOrg, setSavingOrg] = useState(false)
  const [noteBody, setNoteBody] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)

  function load() {
    let active = true
    Promise.all([fetchPartnership(id), fetchAdminUsers(), fetchOrganizations({ pageSize: 200 }), fetchCountries(), fetchPartnershipHistory(id)])
      .then(([p, userList, orgRes, countryList, historyEntries]) => {
        if (!active) return
        setPartnership(p)
        setForm(toForm(p))
        setStatusValue(p.status)
        setAssigneeId(p.assignedToId ? String(p.assignedToId) : '')
        setOrgSlug(p.organizationSlug || '')
        setUsers(userList)
        setOrganizations(orgRes.items)
        setCountries([...countryList].sort((a, b) => a.name.localeCompare(b.name)))
        setHistory(historyEntries)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this partnership. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [id])

  async function refreshHistory() {
    try {
      setHistory(await fetchPartnershipHistory(id))
    } catch {
      // history is supplementary — a failed refresh shouldn't block the page
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await updatePartnership(id, form)
      setPartnership(updated)
      setForm(toForm(updated))
      toast.success('Partnership updated.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this partnership.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatusChange() {
    setSavingStatus(true)
    try {
      const updated = await updatePartnershipStatus(id, statusValue)
      setPartnership(updated)
      toast.success('Status updated.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setSavingStatus(false)
      setConfirmAction(null)
    }
  }

  function handleStatusSubmit() {
    if (statusValue === partnership.status) return
    if (DANGER_STATUSES.has(statusValue)) {
      setConfirmAction('status')
    } else {
      applyStatusChange()
    }
  }

  async function handleAssign() {
    setSavingAssignee(true)
    try {
      const updated = await assignPartnership(id, assigneeId ? Number(assigneeId) : null)
      setPartnership(updated)
      toast.success(assigneeId ? 'Partnership assigned.' : 'Partnership unassigned.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong assigning this partnership.')
    } finally {
      setSavingAssignee(false)
    }
  }

  async function handleLinkOrganization() {
    setSavingOrg(true)
    try {
      const updated = await linkPartnershipOrganization(id, orgSlug || null)
      setPartnership(updated)
      toast.success(orgSlug ? 'Organization linked.' : 'Organization unlinked.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong linking this organization.')
    } finally {
      setSavingOrg(false)
    }
  }

  async function handleAddNote() {
    if (!noteBody.trim()) return
    setSavingNote(true)
    try {
      const updated = await addPartnershipNote(id, noteBody.trim())
      setPartnership(updated)
      setNoteBody('')
      toast.success('Note added.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this note.')
    } finally {
      setSavingNote(false)
    }
  }

  async function handleArchive() {
    try {
      const updated = await archivePartnership(id)
      setPartnership(updated)
      setStatusValue(updated.status)
      toast.success('Partnership archived.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong archiving this partnership.')
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this partnership" description={loadError} />
  if (notFound) return <EmptyState title="Partnership not found" description="This inquiry may have been removed or the URL is incorrect." />
  if (partnership === undefined || form === null) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={partnership.company}
        description={partnership.subject || 'Partnership inquiry'}
        actions={
          <>
            <StatusBadge status={partnership.status} />
            {partnership.status !== 'archived' && (
              <button type="button" onClick={() => setConfirmAction('archive')} className="btn-secondary !px-4 !py-2 text-xs">
                <Archive size={14} /> Archive
              </button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {/* Contact */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Contact</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Contact name">
                <input value={form.contactName} onChange={(e) => setForm({ ...form, contactName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Work email">
                <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Phone" hint="optional">
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Job title" hint="optional">
                <input value={form.jobTitle} onChange={(e) => setForm({ ...form, jobTitle: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Organization (submitted details) */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Organization (as submitted)</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Company">
                <input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Website" hint="optional">
                <input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Country / region" hint="optional">
                <select value={form.countryCode} onChange={(e) => setForm({ ...form, countryCode: e.target.value })} className={inputClass}>
                  <option value="">Not specified</option>
                  {countries.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </div>

          {/* Partnership type + proposal */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Partnership type &amp; proposal</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Partnership type">
                <select value={form.partnershipType} onChange={(e) => setForm({ ...form, partnershipType: e.target.value })} className={inputClass}>
                  <option value="">Not specified</option>
                  {PARTNERSHIP_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Subject / title">
                <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Proposed timing" hint="freeform, e.g. Q1 2027">
                <input value={form.proposedTiming} onChange={(e) => setForm({ ...form, proposedTiming: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Budget range" hint="as submitted, freeform">
                <input value={form.budgetRange} onChange={(e) => setForm({ ...form, budgetRange: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4">
              <Field label="Message">
                <textarea rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Goals / objectives" hint="optional">
                <textarea rows={3} value={form.goals} onChange={(e) => setForm({ ...form, goals: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Dates */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Dates</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Proposed start">
                <input type="date" value={form.proposedStartDate} onChange={(e) => setForm({ ...form, proposedStartDate: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Proposed end">
                <input type="date" value={form.proposedEndDate} onChange={(e) => setForm({ ...form, proposedEndDate: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Actual start">
                <input type="date" value={form.actualStartDate} onChange={(e) => setForm({ ...form, actualStartDate: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Actual end">
                <input type="date" value={form.actualEndDate} onChange={(e) => setForm({ ...form, actualEndDate: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Commercial information */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Commercial information</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Internal reference only — never shown publicly, and not a contract, invoice, or payment record.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Estimated value">
                <input type="number" min="0" value={form.estimatedValue} onChange={(e) => setForm({ ...form, estimatedValue: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Currency" hint="ISO code, e.g. USD">
                <input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase().slice(0, 3) })} className={inputClass} maxLength={3} />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Commercial notes" hint="optional">
                <textarea rows={3} value={form.commercialNotes} onChange={(e) => setForm({ ...form, commercialNotes: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
            <Save size={13} /> {saving ? 'Saving…' : 'Save changes'}
          </button>

          {/* Internal notes */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Staff-only — never visible to the public or the submitting contact.</p>
            <div className="flex gap-2">
              <textarea
                rows={2}
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="e.g. Followed up by email, requested audience demographics…"
                className={`${inputClass} flex-1`}
              />
              <button type="button" onClick={handleAddNote} disabled={savingNote || !noteBody.trim()} className="btn-secondary self-start !px-3 !py-2.5 text-xs disabled:opacity-60">
                <MessageSquarePlus size={14} /> {savingNote ? 'Adding…' : 'Add'}
              </button>
            </div>
            <div className="mt-4 space-y-3">
              {partnership.notes.length === 0 && <p className="text-sm text-charcoal-600/60">No internal notes yet.</p>}
              {partnership.notes.map((note) => (
                <div key={note.id} className="border-l-2 border-taupe-300 pl-3">
                  <p className="text-sm text-charcoal">{note.body}</p>
                  <p className="mt-1 text-xs text-charcoal-600/60">
                    {note.user?.name || 'Unknown'} &middot; {note.createdAt ? formatDate(note.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Activity / history */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Activity</p>
            {history === null && <p className="text-sm text-charcoal-600/60">Loading…</p>}
            {history !== null && history.length === 0 && <p className="text-sm text-charcoal-600/60">No activity recorded yet.</p>}
            {history !== null && history.length > 0 && (
              <ul className="space-y-2 text-sm">
                {history.map((entry) => (
                  <li key={entry.id} className="text-charcoal-600">
                    <span className="font-medium text-charcoal">{entry.action.replace('partnership.', '').replace(/_/g, ' ')}</span>
                    {entry.user && <> by {entry.user}</>}
                    <span className="text-charcoal-600/60"> &middot; {entry.createdAt ? formatDate(entry.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {/* Pipeline status */}
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Pipeline status</p>
            <select value={statusValue} onChange={(e) => setStatusValue(e.target.value)} className={`${inputClass} mt-2`}>
              {PARTNERSHIP_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleStatusSubmit}
              disabled={savingStatus || statusValue === partnership.status}
              className="btn-secondary mt-2 w-full !py-2 text-xs disabled:opacity-60"
            >
              {savingStatus ? 'Updating…' : 'Update status'}
            </button>
          </div>

          {/* Assignment */}
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Assigned owner</p>
            <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} className={`${inputClass} mt-2`}>
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
            <button type="button" onClick={handleAssign} disabled={savingAssignee} className="btn-secondary mt-2 w-full !py-2 text-xs disabled:opacity-60">
              <UserPlus size={13} /> {savingAssignee ? 'Saving…' : 'Save assignment'}
            </button>
          </div>

          {/* Organization link */}
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Linked organization</p>
            <p className="mt-1 text-xs text-charcoal-600/60">Optional — link only when this organization already exists in WSF Organizations.</p>
            <select value={orgSlug} onChange={(e) => setOrgSlug(e.target.value)} className={`${inputClass} mt-2`}>
              <option value="">Not linked</option>
              {organizations.map((o) => (
                <option key={o.slug} value={o.slug}>
                  {o.name}
                </option>
              ))}
            </select>
            <button type="button" onClick={handleLinkOrganization} disabled={savingOrg} className="btn-secondary mt-2 w-full !py-2 text-xs disabled:opacity-60">
              {orgSlug ? <Link2 size={13} /> : <Unlink size={13} />} {savingOrg ? 'Saving…' : orgSlug ? 'Link organization' : 'Unlink organization'}
            </button>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <dl className="space-y-2 text-xs text-charcoal-600">
              <div className="flex justify-between">
                <dt>Submitted</dt>
                <dd>{partnership.submittedAt ? formatDate(partnership.submittedAt) : '—'}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Last updated</dt>
                <dd>{partnership.updatedAt ? formatDate(partnership.updatedAt) : '—'}</dd>
              </div>
            </dl>
          </div>

          <Link to="/admin/partnerships" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all partnerships
          </Link>
        </div>
      </div>

      {confirmAction === 'status' && (
        <ConfirmDialog
          title={`Mark as ${statusValue}?`}
          description="This moves the partnership's pipeline status and is recorded in its activity history."
          confirmLabel="Update status"
          danger
          onConfirm={applyStatusChange}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction === 'archive' && (
        <ConfirmDialog
          title="Archive this partnership?"
          description="It will be removed from the active pipeline view but stays searchable and its history is preserved."
          confirmLabel="Archive"
          danger
          onConfirm={handleArchive}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
