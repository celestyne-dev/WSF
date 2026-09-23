import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Play, Pause, CheckCircle2, Archive, Plus, X } from 'lucide-react'
import {
  fetchSponsor,
  createSponsor,
  updateSponsor,
  updateSponsorStatus,
  deleteSponsor,
  addSponsorPlacement,
  removeSponsorPlacement,
  fetchSponsorHistory,
  fetchSponsorAnalytics,
} from '../../api/sponsors'
import { fetchOrganizations } from '../../api/taxonomies'
import { fetchPartnerships } from '../../api/partnerships'
import { SPONSORSHIP_TYPES, SPONSOR_DISCLOSURE_LABELS, SPONSOR_PLACEMENT_KEYS, SPONSOR_PLACEMENT_LABELS } from '../../constants/sponsors'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import MediaPicker from '../../components/cms/MediaPicker'
import { formatDate } from '../../utils/format'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

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

function blankForm() {
  return {
    campaignName: '',
    organizationSlug: '',
    partnershipId: '',
    internalReference: '',
    publicNameOverride: '',
    publicDescription: '',
    sponsorshipType: '',
    startsAt: '',
    endsAt: '',
    logo: null,
    creative: null,
    sponsorUrl: '',
    ctaLabel: '',
    disclosureLabel: 'Sponsored by',
    publicVisible: false,
    isExclusive: false,
    exclusivityNotes: '',
    tier: '',
    estimatedValue: '',
    currency: '',
    commercialNotes: '',
    internalNotes: '',
  }
}

function toForm(s) {
  return {
    campaignName: s.campaignName,
    organizationSlug: s.organizationSlug || '',
    partnershipId: s.partnershipId ? String(s.partnershipId) : '',
    internalReference: s.internalReference,
    publicNameOverride: s.publicNameOverride,
    publicDescription: s.publicDescription,
    sponsorshipType: s.sponsorshipType,
    startsAt: s.startsAt,
    endsAt: s.endsAt,
    logo: s.logo,
    creative: s.creative,
    sponsorUrl: s.sponsorUrl,
    ctaLabel: s.ctaLabel,
    disclosureLabel: s.disclosureLabel,
    publicVisible: s.publicVisible,
    isExclusive: s.isExclusive,
    exclusivityNotes: s.exclusivityNotes,
    tier: s.tier,
    estimatedValue: s.estimatedValue ?? '',
    currency: s.currency,
    commercialNotes: s.commercialNotes,
    internalNotes: s.internalNotes,
  }
}

const STATUS_ACTIONS = [
  { status: 'active', label: 'Activate', icon: Play },
  { status: 'paused', label: 'Pause', icon: Pause },
  { status: 'completed', label: 'Complete', icon: CheckCircle2 },
  { status: 'archived', label: 'Archive', icon: Archive },
]

export default function AdminSponsorEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [sponsor, setSponsor] = useState(isNew ? null : undefined)
  const [form, setForm] = useState(isNew ? blankForm() : null)
  const [organizations, setOrganizations] = useState([])
  const [partnerships, setPartnerships] = useState([])
  const [history, setHistory] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [newPlacementKey, setNewPlacementKey] = useState(SPONSOR_PLACEMENT_KEYS[0])
  const [addingPlacement, setAddingPlacement] = useState(false)

  function load() {
    let active = true
    Promise.all([
      fetchOrganizations({ pageSize: 200 }),
      fetchPartnerships({ pageSize: 200 }),
      isNew ? Promise.resolve(null) : fetchSponsor(id),
      isNew ? Promise.resolve(null) : fetchSponsorHistory(id),
      isNew ? Promise.resolve(null) : fetchSponsorAnalytics(id),
    ])
      .then(([orgRes, partnershipRes, existing, historyEntries, analyticsSummary]) => {
        if (!active) return
        setOrganizations(orgRes.items)
        setPartnerships(partnershipRes.items)
        if (isNew) return
        if (!existing) {
          setNotFound(true)
          return
        }
        setSponsor(existing)
        setForm(toForm(existing))
        setHistory(historyEntries)
        setAnalytics(analyticsSummary)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this sponsor. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave() {
    setSaving(true)
    try {
      const payload = { ...form, partnershipId: form.partnershipId ? Number(form.partnershipId) : null }
      if (isNew) {
        const created = await createSponsor(payload)
        toast.success('Sponsor created as Draft.')
        navigate(`/admin/sponsors/${created.id}`)
      } else {
        const updated = await updateSponsor(id, payload)
        setSponsor(updated)
        setForm(toForm(updated))
        toast.success('Sponsor updated.')
      }
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this sponsor.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateSponsorStatus(id, status)
      setSponsor(updated)
      toast.success(`Sponsor marked ${status}.`)
      fetchSponsorHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
    }
  }

  function handleStatusClick(status) {
    if (status === 'archived') setConfirmAction({ type: 'status', status })
    else applyStatus(status)
  }

  async function handleAddPlacement() {
    setAddingPlacement(true)
    try {
      const updated = await addSponsorPlacement(id, { placementKey: newPlacementKey, position: sponsor.placements.length })
      setSponsor(updated)
      toast.success('Placement added.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this placement.')
    } finally {
      setAddingPlacement(false)
    }
  }

  async function handleRemovePlacement(placementId) {
    try {
      const updated = await removeSponsorPlacement(id, placementId)
      setSponsor(updated)
      toast.success('Placement removed.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong removing this placement.')
    }
  }

  async function handleDelete() {
    try {
      await deleteSponsor(id)
      toast.success('Draft sponsor deleted.')
      navigate('/admin/sponsors')
    } catch (err) {
      toast.error(err?.apiError?.message || "This sponsor can't be deleted — archive it instead.")
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this sponsor" description={loadError} />
  if (notFound) return <EmptyState title="Sponsor not found" description="This sponsor may have been removed or the URL is incorrect." />
  // Covers the moment right after a new sponsor is created and the page
  // navigates from /new to /:id — `form` is still the stale "new" value
  // (non-null) while `sponsor` hasn't been fetched yet for the new id.
  if (form === null || (!isNew && !sponsor)) return <PageLoader />

  const availableOrgs = organizations
  const availablePartnerships = partnerships

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New sponsor' : sponsor.campaignName}
        description={isNew ? 'Configure a new sponsorship campaign.' : 'Sponsorship campaign — basic info, placements, disclosure, and commercial detail.'}
        actions={!isNew && sponsor && <StatusBadge status={sponsor.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {/* Basic information */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Basic information</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Campaign name">
                <input value={form.campaignName} onChange={(e) => setForm({ ...form, campaignName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Internal reference / title" hint="optional">
                <input value={form.internalReference} onChange={(e) => setForm({ ...form, internalReference: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Public display name override" hint="optional — otherwise shows the Organization's name">
                <input value={form.publicNameOverride} onChange={(e) => setForm({ ...form, publicNameOverride: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Short public description" hint="optional">
                <textarea rows={2} value={form.publicDescription} onChange={(e) => setForm({ ...form, publicDescription: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Organization / Partnership */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Organization &amp; partnership</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Organization">
                <select value={form.organizationSlug} onChange={(e) => setForm({ ...form, organizationSlug: e.target.value })} className={inputClass}>
                  <option value="">Select an organization…</option>
                  {availableOrgs.map((o) => (
                    <option key={o.slug} value={o.slug}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Linked partnership" hint="optional">
                <select value={form.partnershipId} onChange={(e) => setForm({ ...form, partnershipId: e.target.value })} className={inputClass}>
                  <option value="">Not linked</option>
                  {availablePartnerships.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.company} {p.subject ? `— ${p.subject}` : ''}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </div>

          {/* Sponsorship type */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Sponsorship type</p>
            <select value={form.sponsorshipType} onChange={(e) => setForm({ ...form, sponsorshipType: e.target.value })} className={inputClass}>
              <option value="">Not specified</option>
              {SPONSORSHIP_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Campaign dates */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Campaign dates</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Start date" hint="optional">
                <input type="date" value={form.startsAt || ''} onChange={(e) => setForm({ ...form, startsAt: e.target.value })} className={inputClass} />
              </Field>
              <Field label="End date" hint="optional">
                <input type="date" value={form.endsAt || ''} onChange={(e) => setForm({ ...form, endsAt: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Media / creative */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Media &amp; creative</p>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <MediaPicker label="Campaign logo (optional — falls back to Organization logo)" value={form.logo} onChange={(m) => setForm({ ...form, logo: m })} aspect={16 / 9} />
              <MediaPicker label="Banner / card creative (optional)" value={form.creative} onChange={(m) => setForm({ ...form, creative: m })} aspect={16 / 9} />
            </div>
          </div>

          {/* Placements */}
          {!isNew && sponsor && (
            <div className="border border-taupe-200 bg-white p-6">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Placements</p>
              <div className="space-y-2">
                {sponsor.placements.length === 0 && <p className="text-sm text-charcoal-600/60">No placements configured yet — this sponsor won't appear anywhere publicly.</p>}
                {sponsor.placements.map((p) => (
                  <div key={p.id} className="flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                    <span>{SPONSOR_PLACEMENT_LABELS[p.placementKey] || p.placementKey}</span>
                    <button type="button" onClick={() => handleRemovePlacement(p.id)} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Remove placement">
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-2">
                <select value={newPlacementKey} onChange={(e) => setNewPlacementKey(e.target.value)} className={`${inputClass} flex-1`}>
                  {SPONSOR_PLACEMENT_KEYS.map((p) => (
                    <option key={p} value={p}>
                      {SPONSOR_PLACEMENT_LABELS[p]}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={handleAddPlacement} disabled={addingPlacement} className="btn-secondary !px-3 !py-2 text-xs disabled:opacity-60">
                  <Plus size={14} /> Add
                </button>
              </div>
            </div>
          )}
          {isNew && (
            <div className="border border-dashed border-taupe-300 bg-taupe-50 p-6 text-sm text-charcoal-600">
              Save this sponsor first to configure its placements.
            </div>
          )}

          {/* CTA / destination */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">CTA &amp; destination</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Sponsor URL" hint="optional">
                <input type="url" value={form.sponsorUrl} onChange={(e) => setForm({ ...form, sponsorUrl: e.target.value })} placeholder="https://" className={inputClass} />
              </Field>
              <Field label="CTA label" hint="optional, e.g. Visit Sponsor">
                <input value={form.ctaLabel} onChange={(e) => setForm({ ...form, ctaLabel: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Disclosure */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Disclosure</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Shown next to the sponsor on every public placement — never hidden or disguised as editorial content.</p>
            <select value={form.disclosureLabel} onChange={(e) => setForm({ ...form, disclosureLabel: e.target.value })} className={inputClass}>
              {SPONSOR_DISCLOSURE_LABELS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          {/* Commercial information */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Commercial information</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Internal reference only — never shown publicly, and not an invoice, contract, or payment record.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Package / tier" hint="optional">
                <input value={form.tier} onChange={(e) => setForm({ ...form, tier: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Estimated value" hint="optional">
                <input type="number" min="0" value={form.estimatedValue} onChange={(e) => setForm({ ...form, estimatedValue: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Currency" hint="ISO code, e.g. USD">
                <input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase().slice(0, 3) })} maxLength={3} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Commercial notes" hint="optional">
                <textarea rows={2} value={form.commercialNotes} onChange={(e) => setForm({ ...form, commercialNotes: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Exclusivity notes" hint="optional, internal only">
                <textarea rows={2} value={form.exclusivityNotes} onChange={(e) => setForm({ ...form, exclusivityNotes: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.isExclusive} onChange={(e) => setForm({ ...form, isExclusive: e.target.checked })} />
              Exclusive sponsor (internal flag only — not enforced automatically)
            </label>
          </div>

          {/* Internal notes */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <textarea rows={3} value={form.internalNotes} onChange={(e) => setForm({ ...form, internalNotes: e.target.value })} className={inputClass} placeholder="Staff-only notes about this sponsor…" />
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              <Save size={13} /> {saving ? 'Saving…' : isNew ? 'Create sponsor' : 'Save changes'}
            </button>
            {!isNew && sponsor?.status === 'draft' && (
              <button type="button" onClick={() => setConfirmAction({ type: 'delete' })} className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600">
                Delete draft
              </button>
            )}
          </div>

          {/* Activity */}
          {!isNew && (
            <div className="border border-taupe-200 bg-white p-6">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Activity</p>
              {history === null && <p className="text-sm text-charcoal-600/60">Loading…</p>}
              {history !== null && history.length === 0 && <p className="text-sm text-charcoal-600/60">No activity recorded yet.</p>}
              {history !== null && history.length > 0 && (
                <ul className="space-y-2 text-sm">
                  {history.map((entry) => (
                    <li key={entry.id} className="text-charcoal-600">
                      <span className="font-medium text-charcoal">{entry.action.replace('sponsor.', '').replace(/_/g, ' ')}</span>
                      {entry.user && <> by {entry.user}</>}
                      <span className="text-charcoal-600/60"> &middot; {entry.createdAt ? formatDate(entry.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="space-y-4">
          {/* Publishing / status */}
          {!isNew && sponsor && (
            <div className="border border-taupe-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
              <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
                <input
                  type="checkbox"
                  checked={form.publicVisible}
                  onChange={async (e) => {
                    const publicVisible = e.target.checked
                    setForm({ ...form, publicVisible })
                    try {
                      const updated = await updateSponsor(id, { ...form, publicVisible })
                      setSponsor(updated)
                      toast.success(publicVisible ? 'Sponsor is now publicly visible.' : 'Sponsor hidden from public placements.')
                    } catch (err) {
                      toast.error(err?.apiError?.message || 'Something went wrong.')
                    }
                  }}
                />
                Publicly visible
              </label>
              <p className="mt-1 text-xs text-charcoal-600/60">Independent of status — an Active campaign stays hidden until this is on.</p>

              <div className="mt-4 space-y-2">
                {STATUS_ACTIONS.filter((a) => a.status !== sponsor.status).map((a) => (
                  <button key={a.status} type="button" onClick={() => handleStatusClick(a.status)} className="btn-secondary w-full !py-2 text-xs">
                    <a.icon size={13} /> {a.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Live preview */}
          {!isNew && sponsor && (
            <div className="border border-taupe-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Preview</p>
              <div className="mt-3 border border-dashed border-taupe-300 bg-blush-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">{form.disclosureLabel}</p>
                <p className="mt-1 text-sm font-semibold text-charcoal">{form.publicNameOverride || sponsor.organization?.name || 'Sponsor name'}</p>
                {form.publicDescription && <p className="mt-1 text-xs text-charcoal-600">{form.publicDescription}</p>}
                {form.ctaLabel && form.sponsorUrl && (
                  <span className="mt-2 inline-block text-xs font-semibold text-burgundy-600 underline">{form.ctaLabel}</span>
                )}
              </div>
            </div>
          )}

          {/* Analytics */}
          {!isNew && (
            <div className="border border-taupe-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Analytics</p>
              {analytics === null ? (
                <p className="mt-2 text-sm text-charcoal-600/60">Loading…</p>
              ) : (
                <dl className="mt-2 space-y-1 text-sm text-charcoal-600">
                  <div className="flex justify-between">
                    <dt>Impressions</dt>
                    <dd className="font-semibold text-charcoal">{analytics.impressions}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Clicks</dt>
                    <dd className="font-semibold text-charcoal">{analytics.clicks}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Click-through rate</dt>
                    <dd className="font-semibold text-charcoal">{analytics.clickThroughRate == null ? 'Unavailable' : `${analytics.clickThroughRate}%`}</dd>
                  </div>
                </dl>
              )}
            </div>
          )}

          <Link to="/admin/sponsors" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all sponsors
          </Link>
        </div>
      </div>

      {confirmAction?.type === 'status' && (
        <ConfirmDialog
          title={`Mark as ${confirmAction.status}?`}
          description="Archived sponsors are removed from active placements but their record and history are preserved."
          confirmLabel="Archive"
          danger
          onConfirm={() => applyStatus(confirmAction.status)}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction?.type === 'delete' && (
        <ConfirmDialog
          title="Delete this draft sponsor?"
          description="This permanently removes the record. Only unreferenced Draft sponsors can be deleted — established sponsors should be archived instead."
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
