import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { fetchContactInquiry, updateContactInquiryStatus, assignContactInquiry, addContactInquiryNote } from '../../api/contact'
import { fetchAdminUsers } from '../../api/admin'
import { CONTACT_STATUS_LABELS, CONTACT_INQUIRY_TYPE_LABELS } from '../../constants/contact'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

// Mirrors backend CONTACT_STATUS_TRANSITIONS (app/services/contact.py) —
// UX-only guidance; the backend re-validates and is authoritative.
const NEXT_STATUSES = {
  new: ['in_progress', 'spam', 'closed'],
  in_progress: ['resolved', 'spam', 'closed'],
  resolved: ['closed', 'in_progress'],
  closed: ['in_progress'],
  spam: ['new'],
}

function Section({ title, children }) {
  return (
    <div className="border border-taupe-200 bg-white p-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{title}</h3>
      <div className="mt-3 space-y-3">{children}</div>
    </div>
  )
}

function Field({ label, value }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs text-charcoal-600/70">{label}</p>
      <p className="mt-0.5 text-sm text-charcoal">{value}</p>
    </div>
  )
}

export default function AdminContactInquiryDetail() {
  const { id } = useParams()
  const [inquiry, setInquiry] = useState(undefined)
  const [staff, setStaff] = useState([])
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [updatingStatus, setUpdatingStatus] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [noteBody, setNoteBody] = useState('')
  const [savingNote, setSavingNote] = useState(false)

  function load() {
    let active = true
    Promise.all([fetchContactInquiry(id), fetchAdminUsers({ isActive: true, pageSize: 100 })])
      .then(([data, staffRes]) => {
        if (!active) return
        if (!data) {
          setNotFound(true)
          return
        }
        setInquiry(data)
        setStaff(staffRes.items)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this inquiry. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleStatusChange(status) {
    setUpdatingStatus(true)
    try {
      const updated = await updateContactInquiryStatus(id, status)
      setInquiry(updated)
      toast.success(`Marked as ${CONTACT_STATUS_LABELS[status]}.`)
    } catch (err) {
      toast.error(err.apiError?.message || 'Could not update status.')
    } finally {
      setUpdatingStatus(false)
    }
  }

  async function handleAssign(e) {
    const userId = e.target.value ? Number(e.target.value) : null
    setAssigning(true)
    try {
      const updated = await assignContactInquiry(id, userId)
      setInquiry(updated)
      toast.success(userId ? 'Inquiry assigned.' : 'Inquiry unassigned.')
    } catch (err) {
      toast.error(err.apiError?.message || 'Could not update assignment.')
    } finally {
      setAssigning(false)
    }
  }

  async function handleAddNote(e) {
    e.preventDefault()
    if (!noteBody.trim()) return
    setSavingNote(true)
    try {
      const updated = await addContactInquiryNote(id, noteBody.trim())
      setInquiry(updated)
      setNoteBody('')
    } catch (err) {
      toast.error(err.apiError?.message || 'Could not save note.')
    } finally {
      setSavingNote(false)
    }
  }

  if (notFound) return <EmptyState title="Inquiry not found" description="It may have been removed." />
  if (loadError) return <EmptyState title="Couldn't load this inquiry" description={loadError} />
  if (inquiry === undefined) return <PageLoader />

  const nextStatuses = NEXT_STATUSES[inquiry.status] || []

  return (
    <div>
      <AdminPageHeader
        title={inquiry.subject}
        description={`Reference ${inquiry.reference} — received ${formatDate(inquiry.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}`}
        actions={<Link to="/admin/contact" className="btn-secondary !px-4 !py-2 text-xs">Back to inquiries</Link>}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section title="Contact">
            <Field label="Name" value={inquiry.fullName} />
            <Field label="Email" value={<a href={`mailto:${inquiry.email}`} className="text-burgundy-600 hover:underline">{inquiry.email}</a>} />
          </Section>

          <Section title="Inquiry">
            <Field label="Type" value={CONTACT_INQUIRY_TYPE_LABELS[inquiry.inquiryType] || inquiry.inquiryType} />
            <Field label="Subject" value={inquiry.subject} />
            <div>
              <p className="text-xs text-charcoal-600/70">Message</p>
              {/* Public message content is untrusted input — rendered as
                  plain text only, never dangerouslySetInnerHTML. */}
              <p className="mt-1 whitespace-pre-wrap text-sm text-charcoal">{inquiry.message}</p>
            </div>
          </Section>

          <Section title="Internal notes">
            {inquiry.notes.length === 0 && <p className="text-sm text-charcoal-600/70">No internal notes yet.</p>}
            <ul className="space-y-3">
              {inquiry.notes.map((n) => (
                <li key={n.id} className="border-l-2 border-taupe-300 pl-3">
                  <p className="whitespace-pre-wrap text-sm text-charcoal">{n.body}</p>
                  <p className="mt-1 text-xs text-charcoal-600/70">
                    {n.user?.fullName || 'Staff'} — {formatDate(n.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  </p>
                </li>
              ))}
            </ul>
            <form onSubmit={handleAddNote} className="pt-2">
              <label htmlFor="ci-note" className="sr-only">Add an internal note</label>
              <textarea
                id="ci-note"
                rows={3}
                placeholder="Add an internal note (never shown publicly)…"
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
              />
              <button type="submit" disabled={savingNote || !noteBody.trim()} className="btn-secondary mt-2 !px-4 !py-2 text-xs disabled:opacity-60">
                {savingNote ? 'Saving…' : 'Add note'}
              </button>
            </form>
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Workflow">
            <div>
              <p className="text-xs text-charcoal-600/70">Status</p>
              <div className="mt-1"><StatusBadge status={inquiry.status} /></div>
            </div>
            {nextStatuses.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {nextStatuses.map((s) => (
                  <button
                    key={s}
                    type="button"
                    disabled={updatingStatus}
                    onClick={() => handleStatusChange(s)}
                    className="btn-secondary !px-3 !py-1.5 text-xs disabled:opacity-60"
                  >
                    Mark {CONTACT_STATUS_LABELS[s]}
                  </button>
                ))}
              </div>
            )}
            {inquiry.resolvedAt && (
              <Field
                label="Resolved"
                value={`${formatDate(inquiry.resolvedAt, { month: 'short', day: 'numeric', year: 'numeric' })}${inquiry.resolvedBy ? ` by ${inquiry.resolvedBy.fullName}` : ''}`}
              />
            )}

            <div className="pt-2">
              <label htmlFor="ci-assign" className="text-xs text-charcoal-600/70">Assigned to</label>
              <select
                id="ci-assign"
                value={inquiry.assignedTo?.id || ''}
                onChange={handleAssign}
                disabled={assigning}
                className="mt-1 w-full border border-taupe-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">Unassigned</option>
                {staff.map((u) => (
                  <option key={u.id} value={u.id}>{u.name}</option>
                ))}
              </select>
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}
