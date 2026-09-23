import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, X } from 'lucide-react'
import { fetchMember, updateMember, updateMemberStatus, addMemberNote, deleteMember, fetchMemberHistory } from '../../api/community'
import { fetchCountries } from '../../api/geography'
import { fetchTopics } from '../../api/taxonomies'
import { fetchPeople } from '../../api/people'
import { MEMBERSHIP_STATUSES, MEMBERSHIP_TYPES, MEMBERSHIP_SOURCES } from '../../constants/community'
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

function toForm(m) {
  return {
    firstName: m.firstName, lastName: m.lastName, email: m.email,
    professionalTitle: m.professionalTitle, organizationName: m.organizationName, shortBio: m.shortBio,
    websiteUrl: m.websiteUrl, linkedinUrl: m.linkedinUrl, profileImage: m.profileImage,
    countryCode: m.countryCode, city: m.city,
    membershipType: m.membershipType, source: m.source, referralNote: m.referralNote,
    interestSlugs: m.interestSlugs,
    communityUpdatesOptIn: m.communityUpdatesOptIn, directoryOptIn: m.directoryOptIn,
    personId: m.personId ? String(m.personId) : '',
  }
}

export default function AdminMemberDetail() {
  const { id } = useParams()

  const [member, setMember] = useState(undefined)
  const [form, setForm] = useState(null)
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [people, setPeople] = useState([])
  const [personSearch, setPersonSearch] = useState('')
  const [history, setHistory] = useState(null)
  const [noteBody, setNoteBody] = useState('')
  const [addingNote, setAddingNote] = useState(false)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  function load() {
    let active = true
    Promise.all([fetchMember(id), fetchCountries(), fetchTopics(), fetchPeople({ pageSize: 200 }), fetchMemberHistory(id)])
      .then(([m, countryList, topicList, peopleRes, historyEntries]) => {
        if (!active) return
        if (!m) {
          setNotFound(true)
          return
        }
        setMember(m)
        setForm(toForm(m))
        setCountries(countryList)
        setTopics(topicList)
        setPeople(peopleRes.items)
        setHistory(historyEntries)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this member. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  function toggleInterest(slug) {
    setForm((prev) => ({
      ...prev,
      interestSlugs: prev.interestSlugs.includes(slug) ? prev.interestSlugs.filter((s) => s !== slug) : [...prev.interestSlugs, slug],
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      const payload = { ...form, personId: form.personId ? Number(form.personId) : null }
      const updated = await updateMember(id, payload)
      setMember(updated)
      setForm(toForm(updated))
      toast.success('Member updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this member.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateMemberStatus(id, status)
      setMember(updated)
      toast.success(`Member marked ${status}.`)
      fetchMemberHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
    }
  }

  async function handleAddNote() {
    if (!noteBody.trim()) return
    setAddingNote(true)
    try {
      const updated = await addMemberNote(id, noteBody.trim())
      setMember(updated)
      setNoteBody('')
      fetchMemberHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this note.')
    } finally {
      setAddingNote(false)
    }
  }

  async function handleDelete() {
    try {
      await deleteMember(id)
      toast.success('Member record deleted.')
      window.location.href = '/admin/members'
    } catch (err) {
      toast.error(err?.apiError?.message || "This member can't be deleted — archive them instead.")
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this member" description={loadError} />
  if (notFound) return <EmptyState title="Member not found" description="This member may have been removed or the URL is incorrect." />
  if (member === undefined || form === null) return <PageLoader />

  const filteredPeople = personSearch
    ? people.filter((p) => p.name.toLowerCase().includes(personSearch.toLowerCase()))
    : people

  return (
    <div>
      <AdminPageHeader
        title={member.fullName}
        description="Community member record — voluntarily supplied details, membership status, and privacy preferences."
        actions={<StatusBadge status={member.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {/* Member */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Member</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="First name">
                <input value={form.firstName} onChange={(e) => setForm({ ...form, firstName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Last name">
                <input value={form.lastName} onChange={(e) => setForm({ ...form, lastName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Email">
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Professional profile */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Professional profile</p>
            <p className="mb-3 text-xs text-charcoal-600/60">All optional — voluntarily supplied by the member.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Professional title">
                <input value={form.professionalTitle || ''} onChange={(e) => setForm({ ...form, professionalTitle: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Organization / company">
                <input value={form.organizationName || ''} onChange={(e) => setForm({ ...form, organizationName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Website">
                <input type="url" value={form.websiteUrl || ''} onChange={(e) => setForm({ ...form, websiteUrl: e.target.value })} className={inputClass} />
              </Field>
              <Field label="LinkedIn">
                <input type="url" value={form.linkedinUrl || ''} onChange={(e) => setForm({ ...form, linkedinUrl: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Short bio">
                <textarea rows={3} value={form.shortBio || ''} onChange={(e) => setForm({ ...form, shortBio: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <MediaPicker label="Profile image (optional)" value={form.profileImage} onChange={(m) => setForm({ ...form, profileImage: m })} aspect={1} />
            </div>
          </div>

          {/* Geography */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Geography</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Country">
                <select value={form.countryCode || ''} onChange={(e) => setForm({ ...form, countryCode: e.target.value })} className={inputClass}>
                  <option value="">Not specified</option>
                  {countries.map((c) => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="City" hint="optional">
                <input value={form.city || ''} onChange={(e) => setForm({ ...form, city: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* Interests */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Interests</p>
            <div className="flex flex-wrap gap-2">
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

          {/* Membership */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Membership</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Membership type">
                <select value={form.membershipType} onChange={(e) => setForm({ ...form, membershipType: e.target.value })} className={inputClass}>
                  {MEMBERSHIP_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </Field>
              <Field label="Source" hint="optional">
                <select value={form.source || ''} onChange={(e) => setForm({ ...form, source: e.target.value })} className={inputClass}>
                  <option value="">Not specified</option>
                  {MEMBERSHIP_SOURCES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="mt-4">
              <Field label="How did they hear about us?" hint="optional, member-supplied">
                <input value={form.referralNote || ''} onChange={(e) => setForm({ ...form, referralNote: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-charcoal-600/70">Applied</dt>
                <dd className="text-charcoal">{member.appliedAt ? formatDate(member.appliedAt) : '—'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Activated</dt>
                <dd className="text-charcoal">{member.activatedAt ? formatDate(member.activatedAt) : '—'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Left</dt>
                <dd className="text-charcoal">{member.leftAt ? formatDate(member.leftAt) : '—'}</dd>
              </div>
            </dl>
          </div>

          {/* Person link */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Linked public profile</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Optional. Linking never changes this member's or the profile's own public visibility.</p>
            {form.personId && (
              <div className="mb-2 flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                <span>{people.find((p) => String(p.id) === form.personId)?.name || `Person #${form.personId}`}</span>
                <button type="button" onClick={() => setForm({ ...form, personId: '' })} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Unlink">
                  <X size={15} />
                </button>
              </div>
            )}
            {!form.personId && (
              <>
                <input
                  value={personSearch}
                  onChange={(e) => setPersonSearch(e.target.value)}
                  placeholder="Search existing People profiles…"
                  className={inputClass}
                />
                {personSearch && (
                  <div className="mt-2 max-h-40 overflow-y-auto border border-taupe-200">
                    {filteredPeople.slice(0, 10).map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => {
                          setForm({ ...form, personId: String(p.id) })
                          setPersonSearch('')
                        }}
                        className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100"
                      >
                        {p.name} {p.title ? `— ${p.title}` : ''}
                      </button>
                    ))}
                    {filteredPeople.length === 0 && <p className="px-3 py-2 text-sm text-charcoal-600/60">No matches.</p>}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Privacy / directory */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Privacy &amp; directory</p>
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.directoryOptIn} onChange={(e) => setForm({ ...form, directoryOptIn: e.target.checked })} />
              Publicly listed in the member directory
            </label>
            <p className="mt-1 text-xs text-charcoal-600/60">Off by default. Joining WSF never makes a member publicly discoverable on its own.</p>
            <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-charcoal-600/70">Consent given</dt>
                <dd className="text-charcoal">{member.consentGiven ? `Yes — ${member.consentAt ? formatDate(member.consentAt) : ''}` : 'No'}</dd>
              </div>
              <div>
                <dt className="text-charcoal-600/70">Newsletter opt-in at join</dt>
                <dd className="text-charcoal">{member.newsletterOptIn ? 'Yes' : 'No'}</dd>
              </div>
            </dl>
          </div>

          {/* Communication preferences */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Communication preferences</p>
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.communityUpdatesOptIn} onChange={(e) => setForm({ ...form, communityUpdatesOptIn: e.target.checked })} />
              Receives membership-related communication
            </label>
            <p className="mt-1 text-xs text-charcoal-600/60">Distinct from the WSF Weekly newsletter, which is managed separately.</p>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              <Save size={13} /> {saving ? 'Saving…' : 'Save changes'}
            </button>
            {['pending', 'declined'].includes(member.status) && member.notes.length === 0 && (
              <button type="button" onClick={() => setConfirmAction({ type: 'delete' })} className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600">
                Delete record
              </button>
            )}
          </div>

          {/* Internal notes */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Staff-only — never visible publicly.</p>
            <div className="space-y-2">
              {member.notes.length === 0 && <p className="text-sm text-charcoal-600/60">No notes yet.</p>}
              {member.notes.map((n) => (
                <div key={n.id} className="border border-taupe-200 px-3 py-2 text-sm">
                  <p className="text-charcoal">{n.body}</p>
                  <p className="mt-1 text-xs text-charcoal-600/60">
                    {n.user || 'Staff'} &middot; {n.createdAt ? formatDate(n.createdAt, { month: 'short', day: 'numeric', year: 'numeric' }) : ''}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <input value={noteBody} onChange={(e) => setNoteBody(e.target.value)} placeholder="Add an internal note…" className={`${inputClass} flex-1`} />
              <button type="button" onClick={handleAddNote} disabled={addingNote || !noteBody.trim()} className="btn-secondary !px-3 !py-2 text-xs disabled:opacity-60">
                Add
              </button>
            </div>
          </div>

          {/* Activity */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Activity</p>
            {history === null && <p className="text-sm text-charcoal-600/60">Loading…</p>}
            {history !== null && history.length === 0 && <p className="text-sm text-charcoal-600/60">No activity recorded yet.</p>}
            {history !== null && history.length > 0 && (
              <ul className="space-y-2 text-sm">
                {history.map((entry) => (
                  <li key={entry.id} className="text-charcoal-600">
                    <span className="font-medium text-charcoal">{entry.action.replace('member.', '').replace(/_/g, ' ')}</span>
                    {entry.user && <> by {entry.user}</>}
                    <span className="text-charcoal-600/60"> &middot; {entry.createdAt ? formatDate(entry.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Status</p>
            <div className="mt-3 space-y-2">
              {MEMBERSHIP_STATUSES.filter((s) => s !== member.status).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => (s === 'archived' ? setConfirmAction({ type: 'status', status: s }) : applyStatus(s))}
                  className="btn-secondary w-full !py-2 text-xs capitalize"
                >
                  Mark {s}
                </button>
              ))}
            </div>
          </div>

          <Link to="/admin/members" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all members
          </Link>
        </div>
      </div>

      {confirmAction?.type === 'status' && (
        <ConfirmDialog
          title={`Mark as ${confirmAction.status}?`}
          description="Archived members are removed from the public directory but their record and history are preserved."
          confirmLabel="Archive"
          danger
          onConfirm={() => applyStatus(confirmAction.status)}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction?.type === 'delete' && (
        <ConfirmDialog
          title="Delete this member record?"
          description="This permanently removes the record. Only Pending or Declined members without notes can be deleted — established members should be archived instead."
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
