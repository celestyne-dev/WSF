import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { AlertTriangle } from 'lucide-react'
import {
  fetchAdminDirectorySubmission,
  setAdminDirectorySubmissionStatus,
  convertAdminDirectorySubmission,
  addAdminDirectorySubmissionNote,
} from '../../api/directory'
import { DIRECTORY_OWNERSHIP_LABELS, DIRECTORY_LISTING_TYPE_LABELS } from '../../constants/directory'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

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

export default function AdminDirectorySubmissionDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [submission, setSubmission] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [rejectionReason, setRejectionReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [noteBody, setNoteBody] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [customOrgId, setCustomOrgId] = useState('')

  function load() {
    fetchAdminDirectorySubmission(id)
      .then(setSubmission)
      .catch((err) => {
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this submission. Please try again.')
      })
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleReject() {
    if (!rejectionReason.trim()) {
      toast.error('Add a rejection reason first.')
      return
    }
    setBusy(true)
    try {
      const updated = await setAdminDirectorySubmissionStatus(id, 'rejected', rejectionReason.trim())
      setSubmission(updated)
      toast.success('Submission rejected.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not reject this submission.')
    } finally {
      setBusy(false)
    }
  }

  async function handleMarkDuplicate() {
    setBusy(true)
    try {
      const updated = await setAdminDirectorySubmissionStatus(id, 'duplicate')
      setSubmission(updated)
      toast.success('Submission marked as a duplicate.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not update this submission.')
    } finally {
      setBusy(false)
    }
  }

  async function handleConvert(organizationId) {
    setBusy(true)
    try {
      const { listing } = await convertAdminDirectorySubmission(id, organizationId)
      toast.success('Submission converted to a pending directory listing.')
      navigate(`/admin/directory/listings/${listing.id}`)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not convert this submission.')
    } finally {
      setBusy(false)
    }
  }

  async function handleAddNote(e) {
    e.preventDefault()
    if (!noteBody.trim()) return
    setSavingNote(true)
    try {
      const updated = await addAdminDirectorySubmissionNote(id, noteBody.trim())
      setSubmission(updated)
      setNoteBody('')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not save note.')
    } finally {
      setSavingNote(false)
    }
  }

  if (notFound) return <EmptyState title="Submission not found" description="It may have been removed." />
  if (loadError) return <EmptyState title="Couldn't load this submission" description={loadError} />
  if (submission === undefined) return <PageLoader />

  const canAct = submission.status === 'new' || submission.status === 'duplicate'

  return (
    <div>
      <AdminPageHeader
        title={submission.businessName}
        description={`Reference ${submission.reference} — received ${formatDate(submission.createdAt, { month: 'short', day: 'numeric', year: 'numeric' })}`}
        actions={<Link to="/admin/directory/submissions" className="btn-secondary !px-4 !py-2 text-xs">Back to submissions</Link>}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section title="Business claim (self-attested)">
            <Field label="Business name" value={submission.businessName} />
            <Field label="Website" value={submission.website} />
            <Field label="Listing type" value={DIRECTORY_LISTING_TYPE_LABELS[submission.listingType]} />
            <Field label="Ownership classification" value={DIRECTORY_OWNERSHIP_LABELS[submission.ownershipClassification]} />
            <Field label="Location" value={[submission.location, submission.country?.name].filter(Boolean).join(', ')} />
            <div>
              <p className="text-xs text-charcoal-600/70">Description</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-charcoal">{submission.description || '—'}</p>
            </div>
            {submission.keyServices?.length > 0 && (
              <Field label="Key services" value={submission.keyServices.join(', ')} />
            )}
            {submission.serviceModes?.length > 0 && (
              <Field label="Service modes" value={submission.serviceModes.join(', ')} />
            )}
            {submission.categories?.length > 0 && (
              <Field label="Requested categories" value={submission.categories.map((c) => c.name).join(', ')} />
            )}
            <Field label="Public contact email" value={submission.publicContactEmail} />
            <Field label="Public contact phone" value={submission.publicContactPhone} />
          </Section>

          <Section title="Submitter (private — never shown publicly)">
            <Field label="Name" value={submission.submitterName} />
            <Field label="Email" value={<a href={`mailto:${submission.submitterEmail}`} className="text-burgundy-600 hover:underline">{submission.submitterEmail}</a>} />
            <Field label="Role" value={submission.submitterRole} />
          </Section>

          <Section title="Internal notes">
            {submission.notes?.length === 0 && <p className="text-sm text-charcoal-600/70">No internal notes yet.</p>}
            <ul className="space-y-3">
              {submission.notes?.map((n) => (
                <li key={n.id} className="border-l-2 border-taupe-300 pl-3">
                  <p className="whitespace-pre-wrap text-sm text-charcoal">{n.body}</p>
                  <p className="mt-1 text-xs text-charcoal-600/70">
                    {n.user?.fullName || 'Staff'} — {formatDate(n.createdAt, { month: 'short', day: 'numeric', year: 'numeric' })}
                  </p>
                </li>
              ))}
            </ul>
            <form onSubmit={handleAddNote} className="pt-2">
              <label htmlFor="ds-note" className="sr-only">Add an internal note</label>
              <textarea
                id="ds-note"
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
          <Section title="Status">
            <div><StatusBadge status={submission.status} /></div>
            {submission.rejectionReason && <p className="text-xs text-rose-600"><strong>Rejection reason:</strong> {submission.rejectionReason}</p>}
          </Section>

          {submission.possibleDuplicateOrganization && (
            <Section title="Possible duplicate">
              <p className="flex items-start gap-2 text-xs text-amber-700">
                <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
                A similar organization already exists. Nothing was auto-merged — review and decide below.
              </p>
              <p className="text-sm font-medium text-charcoal">{submission.possibleDuplicateOrganization.name}</p>
              <Link to={`/admin/organizations/${submission.possibleDuplicateOrganization.slug}`} className="text-xs font-semibold text-burgundy-600 hover:underline">
                View existing organization
              </Link>
            </Section>
          )}

          {canAct && (
            <Section title="Convert to a directory listing">
              <p className="text-xs text-charcoal-600/70">
                Creates (or links) an Organization and a new, still-pending DirectoryListing. Nothing is published automatically.
              </p>
              {submission.possibleDuplicateOrganization && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handleConvert(submission.possibleDuplicateOrganization.id)}
                  className="btn-primary w-full !px-3 !py-2 text-xs disabled:opacity-60"
                >
                  Link to {submission.possibleDuplicateOrganization.name}
                </button>
              )}
              <button type="button" disabled={busy} onClick={() => handleConvert(undefined)} className="btn-secondary w-full !px-3 !py-2 text-xs disabled:opacity-60">
                Create a new organization
              </button>
              <div className="flex gap-2 pt-1">
                <input
                  value={customOrgId}
                  onChange={(e) => setCustomOrgId(e.target.value)}
                  placeholder="Or enter an Organization ID"
                  className="w-full border border-taupe-300 px-3 py-2 text-xs"
                />
                <button
                  type="button"
                  disabled={busy || !customOrgId}
                  onClick={() => handleConvert(Number(customOrgId))}
                  className="btn-secondary !px-3 !py-2 text-xs disabled:opacity-60"
                >
                  Link
                </button>
              </div>

              <div className="border-t border-taupe-200 pt-3">
                <button type="button" disabled={busy} onClick={handleMarkDuplicate} className="btn-secondary w-full !px-3 !py-2 text-xs disabled:opacity-60">
                  Mark as duplicate (no listing)
                </button>
              </div>

              <div className="border-t border-taupe-200 pt-3">
                <label className="text-xs text-charcoal-600/70">Rejection reason</label>
                <textarea rows={2} value={rejectionReason} onChange={(e) => setRejectionReason(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
                <button type="button" disabled={busy} onClick={handleReject} className="mt-2 w-full !px-3 !py-2 text-xs font-semibold text-ivory bg-rose-600 hover:bg-rose-700 disabled:opacity-60">
                  Reject submission
                </button>
              </div>
            </Section>
          )}

          {submission.resultingListingId && (
            <Link to={`/admin/directory/listings/${submission.resultingListingId}`} className="btn-secondary block w-full !px-3 !py-2 text-center text-xs">
              View resulting listing
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
