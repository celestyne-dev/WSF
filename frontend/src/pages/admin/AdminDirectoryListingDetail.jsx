import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { ExternalLink } from 'lucide-react'
import {
  fetchAdminDirectoryListing,
  updateAdminDirectoryListing,
  setAdminDirectoryListingStatus,
  setAdminDirectoryListingVerification,
  setAdminDirectoryListingFeatured,
  fetchDirectoryCategories,
} from '../../api/directory'
import {
  DIRECTORY_LISTING_TYPES,
  DIRECTORY_LISTING_TYPE_LABELS,
  DIRECTORY_OWNERSHIP_CLASSIFICATIONS,
  DIRECTORY_OWNERSHIP_LABELS,
  DIRECTORY_VERIFICATION_STATUSES,
  DIRECTORY_VERIFICATION_LABELS,
  DIRECTORY_SERVICE_MODES,
  DIRECTORY_SERVICE_MODE_LABELS,
} from '../../constants/directory'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

// Mirrors backend DIRECTORY_LISTING_STATUS_TRANSITIONS (app/services/directory.py) —
// UX-only guidance; the backend re-validates and is authoritative.
const NEXT_STATUSES = {
  pending: ['under_review', 'approved', 'rejected', 'archived'],
  under_review: ['approved', 'rejected', 'pending', 'archived'],
  approved: ['published', 'under_review', 'rejected', 'archived'],
  published: ['archived'],
  rejected: ['pending', 'archived'],
  archived: ['pending'],
}

function Section({ title, children }) {
  return (
    <div className="border border-taupe-200 bg-white p-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{title}</h3>
      <div className="mt-3 space-y-3">{children}</div>
    </div>
  )
}

function toDateTimeLocal(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function AdminDirectoryListingDetail() {
  const { id } = useParams()
  const [listing, setListing] = useState(undefined)
  const [categories, setCategories] = useState([])
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)

  const [rejectionReason, setRejectionReason] = useState('')
  const [verificationNotes, setVerificationNotes] = useState('')
  const [featuredStart, setFeaturedStart] = useState('')
  const [featuredEnd, setFeaturedEnd] = useState('')
  const [busyAction, setBusyAction] = useState(null)

  function load() {
    Promise.all([fetchAdminDirectoryListing(id), fetchDirectoryCategories()])
      .then(([data, cats]) => {
        setListing(data)
        setCategories(cats)
        setForm({
          listingType: data.listingType,
          ownershipClassification: data.ownershipClassification,
          classificationProvenance: data.classificationProvenance,
          serviceSummary: data.serviceSummary || '',
          keyServices: data.keyServices?.length ? data.keyServices : [''],
          serviceModes: data.serviceModes || [],
          categoryIds: data.categories?.map((c) => c.id) || [],
          publicContactEmail: data.publicContactEmail || '',
          publicContactPhone: data.publicContactPhone || '',
        })
        setVerificationNotes(data.verificationNotes || '')
        setFeaturedStart(toDateTimeLocal(data.featuredStartAt))
        setFeaturedEnd(toDateTimeLocal(data.featuredEndAt))
      })
      .catch((err) => {
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this listing. Please try again.')
      })
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await updateAdminDirectoryListing(id, {
        listingType: form.listingType,
        ownershipClassification: form.ownershipClassification,
        classificationProvenance: form.classificationProvenance,
        serviceSummary: form.serviceSummary || null,
        keyServices: form.keyServices.map((s) => s.trim()).filter(Boolean),
        serviceModes: form.serviceModes,
        categoryIds: form.categoryIds,
        publicContactEmail: form.publicContactEmail || null,
        publicContactPhone: form.publicContactPhone || null,
      })
      setListing(updated)
      toast.success('Directory profile saved.')
    } catch (err) {
      toast.error(err.apiError?.message || err?.response?.data?.error?.message || 'Could not save changes.')
    } finally {
      setSaving(false)
    }
  }

  async function handleStatusChange(status) {
    if (status === 'rejected' && !rejectionReason.trim()) {
      toast.error('Add a rejection reason first.')
      return
    }
    setBusyAction(`status-${status}`)
    try {
      const updated = await setAdminDirectoryListingStatus(id, status, status === 'rejected' ? rejectionReason.trim() : undefined)
      setListing(updated)
      toast.success(`Listing marked ${status.replace(/_/g, ' ')}.`)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not update status.')
    } finally {
      setBusyAction(null)
    }
  }

  async function handleVerificationChange(verificationStatus) {
    setBusyAction(`verify-${verificationStatus}`)
    try {
      const updated = await setAdminDirectoryListingVerification(id, verificationStatus, verificationNotes.trim() || undefined)
      setListing(updated)
      toast.success('Verification status updated.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not update verification.')
    } finally {
      setBusyAction(null)
    }
  }

  async function handleFeaturedToggle(featured) {
    setBusyAction('featured')
    try {
      const updated = await setAdminDirectoryListingFeatured(
        id,
        featured,
        featuredStart ? new Date(featuredStart).toISOString() : undefined,
        featuredEnd ? new Date(featuredEnd).toISOString() : undefined,
      )
      setListing(updated)
      toast.success(featured ? 'Listing featured.' : 'Listing un-featured.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not update featured placement.')
    } finally {
      setBusyAction(null)
    }
  }

  if (notFound) return <EmptyState title="Listing not found" description="It may have been removed." />
  if (loadError) return <EmptyState title="Couldn't load this listing" description={loadError} />
  if (listing === undefined || !form) return <PageLoader />

  const nextStatuses = NEXT_STATUSES[listing.status] || []

  return (
    <div>
      <AdminPageHeader
        title={listing.organization?.name || 'Directory listing'}
        description="Directory-specific configuration — Organization identity fields (name, logo, website) are edited on the Organization record itself."
        actions={<Link to="/admin/directory/listings" className="btn-secondary !px-4 !py-2 text-xs">Back to listings</Link>}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section title="Organization">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-charcoal">{listing.organization?.name}</p>
                <p className="text-xs text-charcoal-600/70">{listing.organization?.industry || '—'} · {listing.organization?.country?.name || 'No country set'}</p>
                {listing.organization?.status !== 'published' && (
                  <p className="mt-1 text-xs text-amber-700">
                    This organization is currently <strong>{listing.organization?.status}</strong> — it must be published before this listing can go live publicly.
                  </p>
                )}
              </div>
              <Link to={`/admin/organizations/${listing.organization?.slug}`} className="btn-secondary !px-3 !py-1.5 text-xs">
                Edit organization
              </Link>
            </div>
          </Section>

          <form onSubmit={handleSave}>
            <Section title="Directory profile">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Listing type</label>
                <select
                  value={form.listingType}
                  onChange={(e) => setForm({ ...form, listingType: e.target.value })}
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm"
                >
                  {DIRECTORY_LISTING_TYPES.map((t) => (
                    <option key={t} value={t}>{DIRECTORY_LISTING_TYPE_LABELS[t]}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Service summary</label>
                <textarea
                  rows={3}
                  value={form.serviceSummary}
                  onChange={(e) => setForm({ ...form, serviceSummary: e.target.value })}
                  placeholder="A short, factual summary of what this business offers in the directory."
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Key services</label>
                <div className="mt-1.5 space-y-2">
                  {form.keyServices.map((service, i) => (
                    <div key={i} className="flex gap-2">
                      <input
                        value={service}
                        maxLength={140}
                        onChange={(e) => {
                          const next = [...form.keyServices]
                          next[i] = e.target.value
                          setForm({ ...form, keyServices: next })
                        }}
                        className="w-full border border-taupe-300 px-3 py-2 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setForm({ ...form, keyServices: form.keyServices.filter((_, idx) => idx !== i) })}
                        className="text-xs text-charcoal-600 hover:text-rose-600"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  {form.keyServices.length < 12 && (
                    <button type="button" onClick={() => setForm({ ...form, keyServices: [...form.keyServices, ''] })} className="text-xs font-semibold text-burgundy-600 hover:underline">
                      + Add a service
                    </button>
                  )}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Service modes</label>
                <div className="mt-1.5 flex flex-wrap gap-3">
                  {DIRECTORY_SERVICE_MODES.map((mode) => (
                    <label key={mode} className="flex items-center gap-1.5 text-sm text-charcoal-600">
                      <input
                        type="checkbox"
                        checked={form.serviceModes.includes(mode)}
                        onChange={(e) => {
                          const next = e.target.checked ? [...form.serviceModes, mode] : form.serviceModes.filter((m) => m !== mode)
                          setForm({ ...form, serviceModes: next })
                        }}
                      />
                      {DIRECTORY_SERVICE_MODE_LABELS[mode]}
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Categories</label>
                <div className="mt-1.5 flex flex-wrap gap-3">
                  {categories.map((cat) => (
                    <label key={cat.id} className="flex items-center gap-1.5 text-sm text-charcoal-600">
                      <input
                        type="checkbox"
                        checked={form.categoryIds.includes(cat.id)}
                        onChange={(e) => {
                          const next = e.target.checked ? [...form.categoryIds, cat.id] : form.categoryIds.filter((id2) => id2 !== cat.id)
                          setForm({ ...form, categoryIds: next })
                        }}
                      />
                      {cat.name}
                    </label>
                  ))}
                  {categories.length === 0 && <p className="text-xs text-charcoal-600/70">No directory categories yet.</p>}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Public contact email (opt-in)</label>
                  <input
                    type="email"
                    value={form.publicContactEmail}
                    onChange={(e) => setForm({ ...form, publicContactEmail: e.target.value })}
                    className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Public contact phone (opt-in)</label>
                  <input
                    value={form.publicContactPhone}
                    onChange={(e) => setForm({ ...form, publicContactPhone: e.target.value })}
                    className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <button type="submit" disabled={saving} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
                {saving ? 'Saving…' : 'Save directory profile'}
              </button>
            </Section>
          </form>

          <Section title="Classification">
            <p className="text-xs text-charcoal-600/70">
              An explicit, controlled ownership/leadership claim — never inferred. Provenance tracks whether this is the submitter's own claim or one WSF staff reviewed.
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Ownership classification</label>
                <select
                  value={form.ownershipClassification}
                  onChange={(e) => setForm({ ...form, ownershipClassification: e.target.value })}
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm"
                >
                  {DIRECTORY_OWNERSHIP_CLASSIFICATIONS.map((c) => (
                    <option key={c} value={c}>{DIRECTORY_OWNERSHIP_LABELS[c]}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Provenance</label>
                <select
                  value={form.classificationProvenance}
                  onChange={(e) => setForm({ ...form, classificationProvenance: e.target.value })}
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm"
                >
                  <option value="self_attested">Self-attested by submitter</option>
                  <option value="staff_reviewed">Staff-reviewed</option>
                </select>
              </div>
            </div>
            <p className="text-xs text-charcoal-600/60">Save the directory profile above (in the Directory profile section) to apply classification changes.</p>
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Publishing">
            <div>
              <p className="text-xs text-charcoal-600/70">Status</p>
              <div className="mt-1"><StatusBadge status={listing.status} /></div>
            </div>
            {nextStatuses.includes('rejected') && (
              <div>
                <label className="text-xs text-charcoal-600/70">Rejection reason (required to reject)</label>
                <textarea rows={2} value={rejectionReason} onChange={(e) => setRejectionReason(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
              </div>
            )}
            {listing.rejectionReason && (
              <p className="text-xs text-rose-600"><strong>Previous rejection reason:</strong> {listing.rejectionReason}</p>
            )}
            {nextStatuses.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {nextStatuses.map((s) => (
                  <button
                    key={s}
                    type="button"
                    disabled={busyAction === `status-${s}`}
                    onClick={() => handleStatusChange(s)}
                    className="btn-secondary !px-3 !py-1.5 text-xs disabled:opacity-60"
                  >
                    Mark {s.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            )}
            {listing.publishedAt && <p className="text-xs text-charcoal-600/70">First published {formatDate(listing.publishedAt)}</p>}
          </Section>

          <Section title="Verification">
            <p className="text-xs text-charcoal-600/70">
              Internal WSF review only — never a government, legal, or financial certification.
            </p>
            <div>
              <p className="text-xs text-charcoal-600/70">Current status</p>
              <div className="mt-1"><StatusBadge status={listing.verificationStatus} /></div>
            </div>
            <div>
              <label className="text-xs text-charcoal-600/70">Verification notes (internal only)</label>
              <textarea rows={2} value={verificationNotes} onChange={(e) => setVerificationNotes(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
            </div>
            <div className="flex flex-wrap gap-2">
              {DIRECTORY_VERIFICATION_STATUSES.filter((s) => s !== listing.verificationStatus).map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={busyAction === `verify-${s}`}
                  onClick={() => handleVerificationChange(s)}
                  className="btn-secondary !px-3 !py-1.5 text-xs disabled:opacity-60"
                >
                  Mark {DIRECTORY_VERIFICATION_LABELS[s]}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Promotion">
            <p className="text-xs text-charcoal-600/70">
              Featured placement is commercial/promotional — fully independent of verification. Featuring never implies verification, and verifying never implies payment.
            </p>
            <div>
              <p className="text-xs text-charcoal-600/70">Currently featured</p>
              <p className="mt-1 text-sm font-medium text-charcoal">{listing.isCurrentlyFeatured ? 'Yes — active now' : listing.featured ? 'Scheduled (outside window)' : 'No'}</p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="text-xs text-charcoal-600/70">Featured from</label>
                <input type="datetime-local" value={featuredStart} onChange={(e) => setFeaturedStart(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-xs text-charcoal-600/70">Featured until</label>
                <input type="datetime-local" value={featuredEnd} onChange={(e) => setFeaturedEnd(e.target.value)} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <button type="button" disabled={busyAction === 'featured'} onClick={() => handleFeaturedToggle(true)} className="btn-primary !px-3 !py-1.5 text-xs disabled:opacity-60">
                {listing.featured ? 'Update featured window' : 'Feature this listing'}
              </button>
              {listing.featured && (
                <button type="button" disabled={busyAction === 'featured'} onClick={() => handleFeaturedToggle(false)} className="btn-secondary !px-3 !py-1.5 text-xs disabled:opacity-60">
                  Un-feature
                </button>
              )}
            </div>
          </Section>

          {listing.status === 'published' && listing.organization?.status === 'published' && (
            <a
              href={`/directory/${listing.organization.slug}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-2 border border-taupe-300 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal hover:border-burgundy-400"
            >
              <ExternalLink size={14} /> View live listing
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
