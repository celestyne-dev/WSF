import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { X } from 'lucide-react'
import {
  fetchSubmission, updateSubmission, updateSubmissionStatus, assignSubmissionEditor,
  addSubmissionNote, deleteSubmission, fetchSubmissionHistory, convertSubmissionToArticle,
} from '../../api/submissions'
import { fetchPeople } from '../../api/people'
import { fetchOrganizations, fetchSeries, fetchTopics, fetchAuthors } from '../../api/taxonomies'
import { fetchAdminUsers } from '../../api/admin'
import {
  SUBMISSION_STATUSES, STORY_TYPE_LABELS, CONTENT_ORIGIN_LABELS, AI_INVOLVEMENT_LABELS, VERIFICATION_STATUSES,
  SUBJECT_PERMISSION_STATUSES,
} from '../../constants/submissions'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import { formatDate } from '../../utils/format'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import MediaImage from '../../components/ui/MediaImage'

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

// Statuses an editor can deliberately set from the sidebar. "converted"
// only ever results from the Article-draft handoff, and "published" is
// derived from the linked Article's own state — neither is a manual
// status-button action (the backend rejects both here too).
const MANUAL_STATUSES = SUBMISSION_STATUSES.filter((s) => !['converted', 'published'].includes(s))

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

function toForm(s) {
  return {
    storyType: s.storyType || '',
    topicSlugs: s.topicSlugs,
    seriesId: s.seriesId ? String(s.seriesId) : '',
    recommendedFormat: s.recommendedFormat || '',
    verificationStatus: s.verificationStatus,
    permissionFollowupRequired: s.permissionFollowupRequired,
    mediaFollowupRequired: s.mediaFollowupRequired,
    informationRequestedNote: s.informationRequestedNote || '',
    editorialAssessment: s.editorialAssessment || '',
    subjectPermissionStatus: s.subjectPermissionStatus,
    personId: s.personId ? String(s.personId) : '',
    organizationId: s.organizationId ? String(s.organizationId) : '',
  }
}

export default function AdminStorySubmissionDetail() {
  const { id } = useParams()

  const [submission, setSubmission] = useState(undefined)
  const [form, setForm] = useState(null)
  const [topics, setTopics] = useState([])
  const [series, setSeries] = useState([])
  const [people, setPeople] = useState([])
  const [organizations, setOrganizations] = useState([])
  const [editors, setEditors] = useState([])
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
  const [handoffIncludeMedia, setHandoffIncludeMedia] = useState(true)
  const [converting, setConverting] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  function load() {
    let active = true
    Promise.all([
      fetchSubmission(id), fetchTopics(), fetchSeries(), fetchPeople({ pageSize: 200 }),
      fetchOrganizations({ pageSize: 200 }), fetchAdminUsers(), fetchAuthors({ pageSize: 200 }), fetchSubmissionHistory(id),
    ])
      .then(([s, topicList, seriesList, peopleRes, orgsRes, editorList, authorsRes, historyEntries]) => {
        if (!active) return
        if (!s) {
          setNotFound(true)
          return
        }
        setSubmission(s)
        setForm(toForm(s))
        setTopics(topicList)
        setSeries(seriesList)
        setPeople(peopleRes.items)
        setOrganizations(orgsRes.items)
        setEditors(editorList)
        setAuthors(authorsRes.items)
        setHistory(historyEntries)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this submission. Please try again.')
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
      const updated = await updateSubmission(id, form)
      setSubmission(updated)
      setForm(toForm(updated))
      toast.success('Submission updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this submission.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateSubmissionStatus(id, status)
      setSubmission(updated)
      toast.success(`Submission marked ${status.replace(/_/g, ' ')}.`)
      fetchSubmissionHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
    }
  }

  async function handleAssign(editorId) {
    setAssigning(true)
    try {
      const updated = await assignSubmissionEditor(id, editorId || null)
      setSubmission(updated)
      toast.success(editorId ? 'Editor assigned.' : 'Editor unassigned.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong assigning an editor.')
    } finally {
      setAssigning(false)
    }
  }

  async function handleAddNote() {
    if (!noteBody.trim()) return
    try {
      const updated = await addSubmissionNote(id, noteBody.trim())
      setSubmission(updated)
      setNoteBody('')
      fetchSubmissionHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this note.')
    }
  }

  async function handleDelete() {
    try {
      await deleteSubmission(id)
      toast.success('Submission deleted.')
      window.location.href = '/admin/submissions'
    } catch (err) {
      toast.error(err?.apiError?.message || "This submission can't be deleted — archive it instead.")
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
      const { submission: updatedSubmission, article } = await convertSubmissionToArticle(id, {
        authorId: handoffAuthorId, includeMedia: handoffIncludeMedia,
      })
      setSubmission(updatedSubmission)
      setShowHandoff(false)
      toast.success('Article draft created.')
      fetchSubmissionHistory(id).then(setHistory)
      window.open(`/admin/articles/${article.id}`, '_blank')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong creating the Article draft.')
    } finally {
      setConverting(false)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this submission" description={loadError} />
  if (notFound) return <EmptyState title="Submission not found" description="This submission may have been removed or the URL is incorrect." />
  if (submission === undefined || form === null) return <PageLoader />

  const filteredPeople = personSearch ? people.filter((p) => p.name.toLowerCase().includes(personSearch.toLowerCase())) : []
  const filteredOrgs = orgSearch ? organizations.filter((o) => o.name.toLowerCase().includes(orgSearch.toLowerCase())) : []

  return (
    <div>
      <AdminPageHeader
        title={submission.fullName}
        description={`${submission.reference} — "${submission.title}"`}
        actions={<StatusBadge status={submission.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-6">
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Submitter</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <ReadOnlyField label="Name" value={submission.fullName} />
              <ReadOnlyField label="Email" value={submission.email} />
              <ReadOnlyField label="Country" value={submission.country?.name} />
              <ReadOnlyField label="City" value={submission.city} />
              <ReadOnlyField label="Professional title" value={submission.professionalTitle} />
              <ReadOnlyField label="Organization" value={submission.organizationName} />
              <ReadOnlyField label="LinkedIn / website" value={submission.linkedinUrl || submission.websiteUrl} />
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Story</p>
            <p className="mb-3 text-xs text-charcoal-600/60">The original submitted material — preserved as received, never edited here.</p>
            <div className="space-y-4">
              <ReadOnlyField label="Title" value={submission.title} />
              <ReadOnlyField label="Summary" value={submission.summary} />
              <ReadOnlyField label="Full story" value={submission.body} />
              <ReadOnlyField label="Why it matters" value={submission.whyItMatters} />
              <ReadOnlyField label="Key lessons" value={submission.keyLessons} />
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <ReadOnlyField label="Story type" value={submission.storyType ? STORY_TYPE_LABELS[submission.storyType] : ''} />
              <ReadOnlyField label="Content origin" value={submission.contentOrigin ? CONTENT_ORIGIN_LABELS[submission.contentOrigin] : ''} />
              <ReadOnlyField label="Previously published at" value={submission.previousPublicationUrl} />
              <ReadOnlyField label="AI provenance" value={AI_INVOLVEMENT_LABELS[submission.aiInvolvement]} />
              <ReadOnlyField label="AI provenance note" value={submission.aiProvenanceNote} />
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Subject &amp; people</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <ReadOnlyField label="About the submitter?" value={submission.subjectIsSubmitter ? 'Yes' : 'No'} />
              {!submission.subjectIsSubmitter && <ReadOnlyField label="Subject" value={submission.subjectName} />}
              {!submission.subjectIsSubmitter && <ReadOnlyField label="Relationship to subject" value={submission.subjectRelationship} />}
              {!submission.subjectIsSubmitter && (
                <Field label="Subject permission status">
                  <select value={form.subjectPermissionStatus} onChange={(e) => setForm({ ...form, subjectPermissionStatus: e.target.value })} className={inputClass}>
                    {SUBJECT_PERMISSION_STATUSES.map((s) => (
                      <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                </Field>
              )}
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
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
            <p className="mt-2 text-xs text-charcoal-600/60">Optional. Linking never changes any linked record's own visibility, and never creates a new Person or Organization.</p>
          </div>

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
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Series" hint="editors classify — never required of the public submitter">
                <select value={form.seriesId} onChange={(e) => setForm({ ...form, seriesId: e.target.value })} className={inputClass}>
                  <option value="">Not classified</option>
                  {series.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="Recommended format" hint="optional">
                <input value={form.recommendedFormat} onChange={(e) => setForm({ ...form, recommendedFormat: e.target.value })} placeholder="e.g. Feature article, Profile" className={inputClass} />
              </Field>
            </div>
          </div>

          {submission.mediaItems.length > 0 && (
            <div className="border border-taupe-200 bg-white p-6">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Media &amp; files</p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {submission.mediaItems.map((m) => (
                  <div key={m.id} className="border border-taupe-200 p-3">
                    {m.media && <MediaImage media={m.media} variant="thumbnail" width={300} height={200} alt={m.caption || ''} className="mb-2 h-32 w-full object-cover" />}
                    <p className="text-sm text-charcoal">{m.caption || 'No caption'}</p>
                    <p className="text-xs text-charcoal-600/60">Credit: {m.credit || 'Not specified'}</p>
                    <p className="text-xs text-charcoal-600/60">Rights confirmed: {m.rightsConfirmed ? 'Yes' : 'No'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Consent &amp; rights</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Recorded at submission — never editable here.</p>
            <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
              <p>Permission to review: <span className="font-medium">{submission.consentReviewGiven ? 'Given' : 'Not given'}</span></p>
              <p>Permission to contact: <span className="font-medium">{submission.consentContactGiven ? 'Given' : 'Not given'}</span></p>
              <p>Accuracy confirmed: <span className="font-medium">{submission.consentAccuracyConfirmed ? 'Yes' : 'No'}</span></p>
              {submission.mediaItems.length > 0 && (
                <p>Media rights confirmed: <span className="font-medium">{submission.consentMediaRightsConfirmed ? 'Yes' : 'No'}</span></p>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Editorial review</p>
            <div className="space-y-4">
              <Field label="Editorial assessment" hint="internal only">
                <textarea rows={3} value={form.editorialAssessment} onChange={(e) => setForm({ ...form, editorialAssessment: e.target.value })} className={inputClass} />
              </Field>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Verification">
                  <select value={form.verificationStatus} onChange={(e) => setForm({ ...form, verificationStatus: e.target.value })} className={inputClass}>
                    {VERIFICATION_STATUSES.map((v) => (
                      <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                </Field>
                <div className="flex items-end gap-4">
                  <label className="flex items-center gap-2 text-sm text-charcoal-600">
                    <input type="checkbox" checked={form.permissionFollowupRequired} onChange={(e) => setForm({ ...form, permissionFollowupRequired: e.target.checked })} />
                    Permission follow-up needed
                  </label>
                  <label className="flex items-center gap-2 text-sm text-charcoal-600">
                    <input type="checkbox" checked={form.mediaFollowupRequired} onChange={(e) => setForm({ ...form, mediaFollowupRequired: e.target.checked })} />
                    Media follow-up needed
                  </label>
                </div>
              </div>
              <Field label="Information requested" hint="what's needed from the submitter, when status is Needs Information">
                <textarea rows={2} value={form.informationRequestedNote} onChange={(e) => setForm({ ...form, informationRequestedNote: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            {['submitted', 'reviewing', 'declined', 'withdrawn'].includes(submission.status) && submission.notes.length === 0 && (
              <button type="button" onClick={() => setConfirmAction({ type: 'delete' })} className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600">
                Delete submission
              </button>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Editorial handoff</p>
            {submission.resultingArticle ? (
              <p className="text-sm text-charcoal">
                Linked Article draft: <Link to={`/admin/articles/${submission.resultingArticle.id}`} className="font-semibold text-burgundy-600 hover:underline">{submission.resultingArticle.title}</Link>
                {' '}(<StatusBadge status={submission.resultingArticle.status} />)
              </p>
            ) : submission.status === 'approved' ? (
              showHandoff ? (
                <div className="space-y-3">
                  <Field label="Byline Author" hint="required — an approved submission becomes the profile, never a duplicate Author record">
                    <select value={handoffAuthorId} onChange={(e) => setHandoffAuthorId(e.target.value)} className={inputClass}>
                      <option value="">Select an existing Author…</option>
                      {authors.map((a) => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                      ))}
                    </select>
                  </Field>
                  <label className="flex items-center gap-2 text-sm text-charcoal-600">
                    <input type="checkbox" checked={handoffIncludeMedia} onChange={(e) => setHandoffIncludeMedia(e.target.checked)} />
                    Carry over the first attached image as the hero image
                  </label>
                  <div className="flex gap-2">
                    <button type="button" onClick={handleConvert} disabled={converting} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
                      {converting ? 'Creating…' : 'Create Article draft'}
                    </button>
                    <button type="button" onClick={() => setShowHandoff(false)} className="btn-secondary !px-4 !py-2 text-xs">Cancel</button>
                  </div>
                  <p className="text-xs text-charcoal-600/60">Creates a draft only — never publishes automatically. The original submission is preserved unchanged.</p>
                </div>
              ) : (
                <button type="button" onClick={() => setShowHandoff(true)} className="btn-secondary !px-4 !py-2 text-xs">Create Article draft</button>
              )
            ) : (
              <p className="text-sm text-charcoal-600/60">Only an Approved submission can be converted into an Article draft.</p>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <div className="space-y-2">
              {submission.notes.length === 0 && <p className="text-sm text-charcoal-600/60">No notes yet.</p>}
              {submission.notes.map((n) => (
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
                    <span className="font-medium text-charcoal">{entry.action.replace('submission.', '').replace(/_/g, ' ')}</span>
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
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Submission overview</p>
            <div className="mt-3 space-y-1 text-sm text-charcoal-600">
              <p>Reference: <span className="font-medium text-charcoal">{submission.reference}</span></p>
              <p>Submitted: {submission.submittedAt ? formatDate(submission.submittedAt) : '—'}</p>
              <p>Updated: {submission.updatedAt ? formatDate(submission.updatedAt) : '—'}</p>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Review status</p>
            <div className="mt-3 space-y-2">
              {MANUAL_STATUSES.filter((s) => s !== submission.status).map((s) => (
                <button key={s} type="button" onClick={() => applyStatus(s)} className="btn-secondary w-full !py-2 text-xs capitalize">
                  Mark {s.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Assignment</p>
            <select
              value={submission.assignedEditor?.id || ''}
              onChange={(e) => handleAssign(e.target.value ? Number(e.target.value) : null)}
              disabled={assigning}
              className={`${inputClass} mt-2`}
            >
              <option value="">Unassigned</option>
              {editors.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>

          <Link to="/admin/submissions" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all submissions
          </Link>
        </div>
      </div>

      {confirmAction?.type === 'delete' && (
        <ConfirmDialog
          title="Delete this submission?"
          description="This permanently removes the record. Only Submitted, Reviewing, Declined, or Withdrawn submissions without notes can be deleted."
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
