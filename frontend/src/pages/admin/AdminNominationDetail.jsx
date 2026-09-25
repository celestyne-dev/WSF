import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { X, AlertTriangle } from 'lucide-react'
import {
  fetchNominationDetail, updateNomination, updateNominationStatus, assignNominationReviewer,
  addNominationNote, deleteNomination, fetchNominationHistory, convertNominationToArticle,
} from '../../api/nominations'
import { fetchPeople } from '../../api/people'
import { fetchOrganizations, fetchSeries, fetchTopics, fetchAuthors } from '../../api/taxonomies'
import { fetchAdminUsers } from '../../api/admin'
import { NOMINATION_STATUSES, NOMINEE_AWARENESS_VALUES, NOMINEE_AWARENESS_LABELS, VERIFICATION_STATES } from '../../constants/nominations'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import { formatDate } from '../../utils/format'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

// Statuses an editor can deliberately set from the sidebar. "in_editorial"
// only ever results from the Article-draft handoff, and "published" is
// derived from the linked Article's own state — neither is a manual
// status-button action (the backend rejects both here too).
const MANUAL_STATUSES = NOMINATION_STATUSES.filter((s) => !['in_editorial', 'published'].includes(s))

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

function ReadOnlyField({ label, value }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-charcoal">{value}</p>
    </div>
  )
}

function toForm(n) {
  return {
    topicSlugs: n.topicSlugs,
    seriesId: n.seriesId ? String(n.seriesId) : '',
    editorialAssessment: n.editorialAssessment || '',
    verificationState: n.verificationState,
    verificationNotes: n.verificationNotes || '',
    contactNomineeBeforePublication: n.contactNomineeBeforePublication,
    nomineeAwareness: n.nomineeAwareness,
    personProfileNeeded: n.personProfileNeeded,
    personId: n.personId ? String(n.personId) : '',
    organizationId: n.organizationId ? String(n.organizationId) : '',
  }
}

export default function AdminNominationDetail() {
  const { id } = useParams()

  const [nomination, setNomination] = useState(undefined)
  const [form, setForm] = useState(null)
  const [topics, setTopics] = useState([])
  const [series, setSeries] = useState([])
  const [people, setPeople] = useState([])
  const [organizations, setOrganizations] = useState([])
  const [reviewers, setReviewers] = useState([])
  const [authors, setAuthors] = useState([])
  const [personSearch, setPersonSearch] = useState('')
  const [orgSearch, setOrgSearch] = useState('')
  const [history, setHistory] = useState(null)
  const [noteBody, setNoteBody] = useState('')
  const [saving, setSaving] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [showHandoff, setShowHandoff] = useState(false)
  const [handoffAuthorId, setHandoffAuthorId] = useState('')
  const [converting, setConverting] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  function load() {
    let active = true
    Promise.all([
      fetchNominationDetail(id), fetchTopics(), fetchSeries(), fetchPeople({ pageSize: 200 }),
      fetchOrganizations({ pageSize: 200 }), fetchAdminUsers(), fetchAuthors({ pageSize: 200 }), fetchNominationHistory(id),
    ])
      .then(([n, topicList, seriesList, peopleRes, orgsRes, reviewerList, authorsRes, historyEntries]) => {
        if (!active) return
        if (!n) {
          setNotFound(true)
          return
        }
        setNomination(n)
        setForm(toForm(n))
        setTopics(topicList)
        setSeries(seriesList)
        setPeople(peopleRes.items)
        setOrganizations(orgsRes.items)
        setReviewers(reviewerList)
        setAuthors(authorsRes.items)
        setHistory(historyEntries)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this nomination. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await updateNomination(id, form)
      setNomination(updated)
      setForm(toForm(updated))
      toast.success('Nomination updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this nomination.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateNominationStatus(id, status)
      setNomination(updated)
      toast.success(`Nomination marked ${status.replace(/_/g, ' ')}.`)
      fetchNominationHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
    }
  }

  async function handleAssign(reviewerId) {
    setAssigning(true)
    try {
      const updated = await assignNominationReviewer(id, reviewerId || null)
      setNomination(updated)
      toast.success(reviewerId ? 'Reviewer assigned.' : 'Reviewer unassigned.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong assigning a reviewer.')
    } finally {
      setAssigning(false)
    }
  }

  async function handleAddNote() {
    if (!noteBody.trim()) return
    try {
      const updated = await addNominationNote(id, noteBody.trim())
      setNomination(updated)
      setNoteBody('')
      fetchNominationHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this note.')
    }
  }

  async function handleDelete() {
    try {
      await deleteNomination(id)
      toast.success('Nomination deleted.')
      window.location.href = '/admin/nominations'
    } catch (err) {
      toast.error(err?.apiError?.message || "This nomination can't be deleted — archive it instead.")
    } finally {
      setConfirmAction(null)
    }
  }

  async function handleConvert() {
    if (!handoffAuthorId) {
      toast.error('Select an Author for the byline.')
      return
    }
    setConverting(true)
    try {
      const { nomination: updatedNomination, article } = await convertNominationToArticle(id, { authorId: handoffAuthorId })
      setNomination(updatedNomination)
      setShowHandoff(false)
      toast.success('Article draft created.')
      fetchNominationHistory(id).then(setHistory)
      window.open(`/admin/articles/${article.id}`, '_blank')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong creating the Article draft.')
    } finally {
      setConverting(false)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this nomination" description={loadError} />
  if (notFound) return <EmptyState title="Nomination not found" description="This nomination may have been removed or the URL is incorrect." />
  if (nomination === undefined || form === null) return <PageLoader />

  const filteredPeople = personSearch ? people.filter((p) => p.name.toLowerCase().includes(personSearch.toLowerCase())) : []
  const filteredOrgs = orgSearch ? organizations.filter((o) => o.name.toLowerCase().includes(orgSearch.toLowerCase())) : []

  return (
    <div>
      <AdminPageHeader
        title={nomination.nomineeName}
        description={`${nomination.reference} — nominated by ${nomination.nominatorName}`}
        actions={<StatusBadge status={nomination.status} />}
      />

      {nomination.possibleDuplicate && (
        <div className="mb-4 flex items-center gap-2 border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle size={16} />
          Possible existing nominee — another nomination shares this name. Check Duplicate &amp; Person linking below before approving.
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-6">
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Nominee</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <ReadOnlyField label="Name" value={nomination.nomineeName} />
              <ReadOnlyField label="Country" value={nomination.country?.name} />
              <ReadOnlyField label="City" value={nomination.city} />
              <ReadOnlyField label="Professional title" value={nomination.professionalTitle} />
              <ReadOnlyField label="Organization" value={nomination.organizationName} />
              <ReadOnlyField label="Website / LinkedIn" value={nomination.websiteUrl || nomination.linkedinUrl} />
              <ReadOnlyField label="Nominee email (admin only, never public)" value={nomination.nomineeEmail} />
            </div>
            {nomination.shortBio && <div className="mt-4"><ReadOnlyField label="Short biography / context" value={nomination.shortBio} /></div>}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Nomination reason &amp; achievements</p>
            <p className="mb-3 text-xs text-charcoal-600/60">As submitted — preserved as received, never edited here.</p>
            <div className="space-y-4">
              <ReadOnlyField label="Nomination summary" value={nomination.nominationSummary} />
              <ReadOnlyField label="What has she done / key achievements" value={nomination.achievements} />
              <ReadOnlyField label="Why is it significant" value={nomination.whySignificant} />
              <ReadOnlyField label="Who has been impacted" value={nomination.whoImpacted} />
            </div>
          </div>

          {nomination.supportingLinks.length > 0 && (
            <div className="border border-taupe-200 bg-white p-6">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Supporting evidence</p>
              <ul className="space-y-1.5 text-sm">
                {nomination.supportingLinks.map((l, i) => (
                  <li key={i}>
                    <a href={l.url} target="_blank" rel="noreferrer" className="text-burgundy-600 hover:underline">
                      {l.label || l.url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Topics &amp; series</p>
            <Field label="Topics">
              <div className="mt-1 flex flex-wrap gap-2">
                {topics.map((t) => (
                  <button key={t.slug} type="button" onClick={() => toggleTopic(t.slug)} className={`px-2.5 py-1 text-xs font-medium ${form.topicSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
                    {t.name}
                  </button>
                ))}
              </div>
            </Field>
            <div className="mt-4">
              <Field label="Series" hint="editors remain authoritative — a public suggestion is only a starting point">
                <select value={form.seriesId} onChange={(e) => setForm({ ...form, seriesId: e.target.value })} className={inputClass}>
                  <option value="">Not classified</option>
                  {series.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Nominator</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Private — never shown publicly.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <ReadOnlyField label="Name" value={nomination.nominatorName} />
              <ReadOnlyField label="Email" value={nomination.nominatorEmail} />
              <ReadOnlyField label="Organization" value={nomination.nominatorOrganization} />
              <ReadOnlyField label="Relationship to nominee" value={nomination.relationshipToNominee} />
              <ReadOnlyField label="Self-nomination?" value={nomination.isSelfNomination ? 'Yes' : 'No'} />
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Nominee awareness">
                <select value={form.nomineeAwareness} onChange={(e) => setForm({ ...form, nomineeAwareness: e.target.value })} className={inputClass}>
                  {NOMINEE_AWARENESS_VALUES.map((v) => (
                    <option key={v} value={v}>{NOMINEE_AWARENESS_LABELS[v]}</option>
                  ))}
                </select>
              </Field>
              <Field label="Before publication">
                <label className="flex h-[42px] items-center gap-2 text-sm text-charcoal-600">
                  <input type="checkbox" checked={form.contactNomineeBeforePublication} onChange={(e) => setForm({ ...form, contactNomineeBeforePublication: e.target.checked })} />
                  Contact nominee before publication
                </label>
              </Field>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
              <p>Accuracy confirmed: <span className="font-medium">{nomination.consentAccuracyConfirmed ? 'Yes' : 'No'}</span></p>
              <p>Permission to review: <span className="font-medium">{nomination.consentReviewGiven ? 'Given' : 'Not given'}</span></p>
              <p>Permission to contact: <span className="font-medium">{nomination.consentContactGiven ? 'Given' : 'Not given'}</span></p>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Duplicate &amp; Person linking</p>
            {nomination.relatedNominations.length > 0 && (
              <div className="mb-4">
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Other nominations for this nominee</p>
                <ul className="space-y-1 text-sm">
                  {nomination.relatedNominations.map((r) => (
                    <li key={r.id}>
                      <Link to={`/admin/nominations/${r.id}`} className="text-burgundy-600 hover:underline">{r.reference}</Link>
                      {' '}— <StatusBadge status={r.status} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Linked Person profile</label>
                {form.personId ? (
                  <div className="mt-1.5 flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                    <span>{people.find((p) => String(p.id) === form.personId)?.name || `Person #${form.personId}`}</span>
                    <button type="button" onClick={() => setForm({ ...form, personId: '' })} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Unlink">
                      <X size={15} />
                    </button>
                  </div>
                ) : (
                  <>
                    <input value={personSearch} onChange={(e) => setPersonSearch(e.target.value)} placeholder="Search People profiles…" className={`${inputClass} mt-1.5`} />
                    {personSearch && (
                      <div className="mt-1 max-h-32 overflow-y-auto border border-taupe-200">
                        {filteredPeople.slice(0, 8).map((p) => (
                          <button key={p.id} type="button" onClick={() => { setForm({ ...form, personId: String(p.id) }); setPersonSearch('') }} className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100">
                            {p.name}
                          </button>
                        ))}
                        {filteredPeople.length === 0 && <p className="px-3 py-2 text-sm text-charcoal-600/60">No matches.</p>}
                      </div>
                    )}
                  </>
                )}
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Linked Organization</label>
                {form.organizationId ? (
                  <div className="mt-1.5 flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                    <span>{organizations.find((o) => String(o.id) === form.organizationId)?.name || `Organization #${form.organizationId}`}</span>
                    <button type="button" onClick={() => setForm({ ...form, organizationId: '' })} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Unlink">
                      <X size={15} />
                    </button>
                  </div>
                ) : (
                  <>
                    <input value={orgSearch} onChange={(e) => setOrgSearch(e.target.value)} placeholder="Search Organizations…" className={`${inputClass} mt-1.5`} />
                    {orgSearch && (
                      <div className="mt-1 max-h-32 overflow-y-auto border border-taupe-200">
                        {filteredOrgs.slice(0, 8).map((o) => (
                          <button key={o.id} type="button" onClick={() => { setForm({ ...form, organizationId: String(o.id) }); setOrgSearch('') }} className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100">
                            {o.name}
                          </button>
                        ))}
                        {filteredOrgs.length === 0 && <p className="px-3 py-2 text-sm text-charcoal-600/60">No matches.</p>}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.personProfileNeeded} onChange={(e) => setForm({ ...form, personProfileNeeded: e.target.checked })} />
              A new Person profile should eventually be created (via People CMS)
            </label>
            <p className="mt-2 text-xs text-charcoal-600/60">Optional. Linking never changes any linked record's own visibility, and never creates a new Person or Organization.</p>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Verification</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Verification status">
                <select value={form.verificationState} onChange={(e) => setForm({ ...form, verificationState: e.target.value })} className={inputClass}>
                  {VERIFICATION_STATES.map((v) => (
                    <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Verification notes" hint="internal only">
                <textarea rows={3} value={form.verificationNotes} onChange={(e) => setForm({ ...form, verificationNotes: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Editorial review</p>
            <Field label="Editorial assessment" hint="internal only">
              <textarea rows={3} value={form.editorialAssessment} onChange={(e) => setForm({ ...form, editorialAssessment: e.target.value })} className={inputClass} />
            </Field>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            {['submitted', 'reviewing', 'declined', 'withdrawn'].includes(nomination.status) && nomination.notes.length === 0 && (
              <button type="button" onClick={() => setConfirmAction({ type: 'delete' })} className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600">
                Delete nomination
              </button>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Editorial handoff</p>
            {nomination.resultingArticle ? (
              <p className="text-sm text-charcoal">
                Linked Article draft: <Link to={`/admin/articles/${nomination.resultingArticle.id}`} className="font-semibold text-burgundy-600 hover:underline">{nomination.resultingArticle.title}</Link>
                {' '}(<StatusBadge status={nomination.resultingArticle.status} />)
              </p>
            ) : nomination.status === 'approved' ? (
              showHandoff ? (
                <div className="space-y-3">
                  <Field label="Byline Author" hint="required — nominee/nominator are never auto-promoted to an Author">
                    <select value={handoffAuthorId} onChange={(e) => setHandoffAuthorId(e.target.value)} className={inputClass}>
                      <option value="">Select an existing Author…</option>
                      {authors.map((a) => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                      ))}
                    </select>
                  </Field>
                  <div className="flex gap-2">
                    <button type="button" onClick={handleConvert} disabled={converting} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
                      {converting ? 'Creating…' : 'Create Article draft'}
                    </button>
                    <button type="button" onClick={() => setShowHandoff(false)} className="btn-secondary !px-4 !py-2 text-xs">Cancel</button>
                  </div>
                  <p className="text-xs text-charcoal-600/60">Creates a draft only — never publishes automatically. The original nomination is preserved unchanged.</p>
                </div>
              ) : (
                <button type="button" onClick={() => setShowHandoff(true)} className="btn-secondary !px-4 !py-2 text-xs">Create Article draft</button>
              )
            ) : (
              <p className="text-sm text-charcoal-600/60">Only an Approved nomination can be converted into an Article draft.</p>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <div className="space-y-2">
              {nomination.notes.length === 0 && <p className="text-sm text-charcoal-600/60">No notes yet.</p>}
              {nomination.notes.map((n) => (
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
              <button type="button" onClick={handleAddNote} disabled={!noteBody.trim()} className="btn-secondary !px-3 !py-2 text-xs disabled:opacity-60">
                Add
              </button>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Activity</p>
            {history === null && <p className="text-sm text-charcoal-600/60">Loading…</p>}
            {history !== null && history.length === 0 && <p className="text-sm text-charcoal-600/60">No activity recorded yet.</p>}
            {history !== null && history.length > 0 && (
              <ul className="space-y-2 text-sm">
                {history.map((entry) => (
                  <li key={entry.id} className="text-charcoal-600">
                    <span className="font-medium text-charcoal">{entry.action.replace('nomination.', '').replace(/_/g, ' ')}</span>
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
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Nomination overview</p>
            <div className="mt-3 space-y-1 text-sm text-charcoal-600">
              <p>Reference: <span className="font-medium text-charcoal">{nomination.reference}</span></p>
              <p>Submitted: {nomination.submittedAt ? formatDate(nomination.submittedAt) : '—'}</p>
              <p>Updated: {nomination.updatedAt ? formatDate(nomination.updatedAt) : '—'}</p>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Review status</p>
            <div className="mt-3 space-y-2">
              {MANUAL_STATUSES.filter((s) => s !== nomination.status).map((s) => (
                <button key={s} type="button" onClick={() => applyStatus(s)} className="btn-secondary w-full !py-2 text-xs capitalize">
                  Mark {s.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Assigned reviewer</p>
            <select
              value={nomination.assignedReviewer?.id || ''}
              onChange={(e) => handleAssign(e.target.value ? Number(e.target.value) : null)}
              disabled={assigning}
              className={`${inputClass} mt-2`}
            >
              <option value="">Unassigned</option>
              {reviewers.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>

          <Link to="/admin/nominations" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all nominations
          </Link>
        </div>
      </div>

      {confirmAction?.type === 'delete' && (
        <ConfirmDialog
          title="Delete this nomination?"
          description="This permanently removes the record. Only Submitted, Reviewing, Declined, or Withdrawn nominations without notes can be deleted."
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
