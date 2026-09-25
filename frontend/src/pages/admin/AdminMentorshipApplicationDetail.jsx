import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, X } from 'lucide-react'
import {
  fetchApplication, updateApplication, updateApplicationStatus, addApplicationNote, deleteApplication, fetchApplicationHistory,
} from '../../api/mentorship'
import { fetchCountries } from '../../api/geography'
import { fetchTopics } from '../../api/taxonomies'
import { fetchPeople } from '../../api/people'
import { fetchMembers } from '../../api/community'
import { APPLICATION_STATUSES, CAREER_STAGES, MEETING_FREQUENCIES, MENTORSHIP_FORMATS } from '../../constants/mentorship'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
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

function toForm(a) {
  return {
    firstName: a.firstName, lastName: a.lastName, email: a.email,
    professionalTitle: a.professionalTitle, organizationName: a.organizationName, industry: a.industry,
    yearsExperience: a.yearsExperience ?? '', linkedinUrl: a.linkedinUrl, websiteUrl: a.websiteUrl,
    backgroundText: a.backgroundText, goalsText: a.goalsText, supportOfferedText: a.supportOfferedText,
    careerStage: a.careerStage, careerStagesSupported: a.careerStagesSupported,
    countryCode: a.countryCode, timezone: a.timezone, meetingFrequency: a.meetingFrequency,
    mentorshipFormat: a.mentorshipFormat, availabilityNote: a.availabilityNote,
    mentorCapacity: a.mentorCapacity ?? '', mentorActive: a.mentorActive,
    topicSlugs: a.topicSlugs, memberId: a.memberId ? String(a.memberId) : '', personId: a.personId ? String(a.personId) : '',
  }
}

export default function AdminMentorshipApplicationDetail() {
  const { id } = useParams()

  const [application, setApplication] = useState(undefined)
  const [form, setForm] = useState(null)
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [people, setPeople] = useState([])
  const [members, setMembers] = useState([])
  const [personSearch, setPersonSearch] = useState('')
  const [memberSearch, setMemberSearch] = useState('')
  const [history, setHistory] = useState(null)
  const [noteBody, setNoteBody] = useState('')
  const [addingNote, setAddingNote] = useState(false)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  function load() {
    let active = true
    Promise.all([
      fetchApplication(id), fetchCountries(), fetchTopics(),
      fetchPeople({ pageSize: 200 }), fetchMembers({ pageSize: 200 }), fetchApplicationHistory(id),
    ])
      .then(([a, countryList, topicList, peopleRes, membersRes, historyEntries]) => {
        if (!active) return
        if (!a) {
          setNotFound(true)
          return
        }
        setApplication(a)
        setForm(toForm(a))
        setCountries(countryList)
        setTopics(topicList)
        setPeople(peopleRes.items)
        setMembers(membersRes.items)
        setHistory(historyEntries)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this application. Please try again.')
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

  function toggleCareerStageSupported(stage) {
    setForm((prev) => ({
      ...prev,
      careerStagesSupported: prev.careerStagesSupported.includes(stage)
        ? prev.careerStagesSupported.filter((s) => s !== stage)
        : [...prev.careerStagesSupported, stage],
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      const payload = { ...form, memberId: form.memberId ? Number(form.memberId) : null, personId: form.personId ? Number(form.personId) : null }
      const updated = await updateApplication(id, payload)
      setApplication(updated)
      setForm(toForm(updated))
      toast.success('Application updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this application.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateApplicationStatus(id, status)
      setApplication(updated)
      toast.success(`Application marked ${status}.`)
      fetchApplicationHistory(id).then(setHistory)
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
      const updated = await addApplicationNote(id, noteBody.trim())
      setApplication(updated)
      setNoteBody('')
      fetchApplicationHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this note.')
    } finally {
      setAddingNote(false)
    }
  }

  async function handleDelete() {
    try {
      await deleteApplication(id)
      toast.success('Application deleted.')
      window.location.href = '/admin/mentorship/applications'
    } catch (err) {
      toast.error(err?.apiError?.message || "This application can't be deleted — archive it instead.")
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this application" description={loadError} />
  if (notFound) return <EmptyState title="Application not found" description="This application may have been removed or the URL is incorrect." />
  if (application === undefined || form === null) return <PageLoader />

  const isMentor = application.role === 'mentor'
  const filteredPeople = personSearch ? people.filter((p) => p.name.toLowerCase().includes(personSearch.toLowerCase())) : []
  const filteredMembers = memberSearch ? members.filter((m) => m.fullName.toLowerCase().includes(memberSearch.toLowerCase())) : []

  return (
    <div>
      <AdminPageHeader
        title={application.fullName}
        description={`${isMentor ? 'Mentor' : 'Mentee'} application to ${application.program?.name || 'a mentorship program'}.`}
        actions={<StatusBadge status={application.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-6">
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Applicant</p>
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

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Program</p>
            <p className="text-sm text-charcoal">{application.program?.name}</p>
            <p className="mt-1 text-xs text-charcoal-600/60 capitalize">Applying as {application.role}</p>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Professional profile</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Professional title">
                <input value={form.professionalTitle || ''} onChange={(e) => setForm({ ...form, professionalTitle: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Organization">
                <input value={form.organizationName || ''} onChange={(e) => setForm({ ...form, organizationName: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Industry">
                <input value={form.industry || ''} onChange={(e) => setForm({ ...form, industry: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Years of experience" hint="optional">
                <input type="number" min="0" value={form.yearsExperience} onChange={(e) => setForm({ ...form, yearsExperience: e.target.value })} className={inputClass} />
              </Field>
              <Field label="LinkedIn">
                <input type="url" value={form.linkedinUrl || ''} onChange={(e) => setForm({ ...form, linkedinUrl: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Website">
                <input type="url" value={form.websiteUrl || ''} onChange={(e) => setForm({ ...form, websiteUrl: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Expertise &amp; goals</p>
            <div className="space-y-4">
              <Field label="Background">
                <textarea rows={3} value={form.backgroundText || ''} onChange={(e) => setForm({ ...form, backgroundText: e.target.value })} className={inputClass} />
              </Field>
              <Field label={isMentor ? 'Why they want to mentor' : 'Mentorship goals'}>
                <textarea rows={3} value={form.goalsText || ''} onChange={(e) => setForm({ ...form, goalsText: e.target.value })} className={inputClass} />
              </Field>
              {isMentor && (
                <Field label="What they can support mentees with">
                  <textarea rows={2} value={form.supportOfferedText || ''} onChange={(e) => setForm({ ...form, supportOfferedText: e.target.value })} className={inputClass} />
                </Field>
              )}
            </div>
            <div className="mt-4">
              <Field label="Topics" hint={isMentor ? 'areas they can mentor in' : 'areas of interest'}>
                <div className="mt-1 flex flex-wrap gap-2">
                  {topics.map((t) => (
                    <button key={t.slug} type="button" onClick={() => toggleTopic(t.slug)} className={`px-2.5 py-1 text-xs font-medium ${form.topicSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
                      {t.name}
                    </button>
                  ))}
                </div>
              </Field>
            </div>
            <div className="mt-4">
              {isMentor ? (
                <Field label="Career stages comfortable mentoring">
                  <div className="mt-1 flex flex-wrap gap-2">
                    {CAREER_STAGES.map((s) => (
                      <button key={s} type="button" onClick={() => toggleCareerStageSupported(s)} className={`px-2.5 py-1 text-xs font-medium ${form.careerStagesSupported.includes(s) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </Field>
              ) : (
                <Field label="Career stage">
                  <select value={form.careerStage || ''} onChange={(e) => setForm({ ...form, careerStage: e.target.value })} className={inputClass}>
                    <option value="">Not specified</option>
                    {CAREER_STAGES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </Field>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Matching preferences</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Country">
                <select value={form.countryCode || ''} onChange={(e) => setForm({ ...form, countryCode: e.target.value })} className={inputClass}>
                  <option value="">Not specified</option>
                  {countries.map((c) => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="Timezone" hint="optional">
                <input value={form.timezone || ''} onChange={(e) => setForm({ ...form, timezone: e.target.value })} placeholder="e.g. Africa/Nairobi" className={inputClass} />
              </Field>
              <Field label="Meeting frequency" hint="optional">
                <select value={form.meetingFrequency || ''} onChange={(e) => setForm({ ...form, meetingFrequency: e.target.value })} className={inputClass}>
                  <option value="">Not specified</option>
                  {MEETING_FREQUENCIES.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </Field>
              <Field label="Format" hint="optional">
                <select value={form.mentorshipFormat || ''} onChange={(e) => setForm({ ...form, mentorshipFormat: e.target.value })} className={inputClass}>
                  <option value="">Not specified</option>
                  {MENTORSHIP_FORMATS.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Availability note" hint="optional">
                <textarea rows={2} value={form.availabilityNote || ''} onChange={(e) => setForm({ ...form, availabilityNote: e.target.value })} className={inputClass} />
              </Field>
            </div>
            {isMentor && (
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Mentor capacity" hint="max concurrent mentees">
                  <input type="number" min="0" value={form.mentorCapacity} onChange={(e) => setForm({ ...form, mentorCapacity: e.target.value })} className={inputClass} />
                </Field>
                <Field label="Accepting new matches">
                  <label className="flex h-[42px] items-center gap-2 text-sm text-charcoal-600">
                    <input type="checkbox" checked={form.mentorActive} onChange={(e) => setForm({ ...form, mentorActive: e.target.checked })} />
                    Active ({application.activeMenteeCount} current mentee{application.activeMenteeCount === 1 ? '' : 's'})
                  </label>
                </Field>
              </div>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Linked records</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Optional. Linking never changes any linked record's own visibility.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Community Member</label>
                {form.memberId ? (
                  <div className="mt-1.5 flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                    <span>{members.find((m) => String(m.id) === form.memberId)?.fullName || `Member #${form.memberId}`}</span>
                    <button type="button" onClick={() => setForm({ ...form, memberId: '' })} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Unlink">
                      <X size={15} />
                    </button>
                  </div>
                ) : (
                  <>
                    <input value={memberSearch} onChange={(e) => setMemberSearch(e.target.value)} placeholder="Search Community members…" className={`${inputClass} mt-1.5`} />
                    {memberSearch && (
                      <div className="mt-1 max-h-32 overflow-y-auto border border-taupe-200">
                        {filteredMembers.slice(0, 8).map((m) => (
                          <button key={m.id} type="button" onClick={() => { setForm({ ...form, memberId: String(m.id) }); setMemberSearch('') }} className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100">
                            {m.fullName}
                          </button>
                        ))}
                        {filteredMembers.length === 0 && <p className="px-3 py-2 text-sm text-charcoal-600/60">No matches.</p>}
                      </div>
                    )}
                  </>
                )}
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Person profile</label>
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
                            {p.name} {p.title ? `— ${p.title}` : ''}
                          </button>
                        ))}
                        {filteredPeople.length === 0 && <p className="px-3 py-2 text-sm text-charcoal-600/60">No matches.</p>}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              <Save size={13} /> {saving ? 'Saving…' : 'Save changes'}
            </button>
            {['submitted', 'reviewing', 'declined', 'withdrawn'].includes(application.status) && application.notes.length === 0 && (
              <button type="button" onClick={() => setConfirmAction({ type: 'delete' })} className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600">
                Delete application
              </button>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <div className="space-y-2">
              {application.notes.length === 0 && <p className="text-sm text-charcoal-600/60">No notes yet.</p>}
              {application.notes.map((n) => (
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

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Activity</p>
            {history === null && <p className="text-sm text-charcoal-600/60">Loading…</p>}
            {history !== null && history.length === 0 && <p className="text-sm text-charcoal-600/60">No activity recorded yet.</p>}
            {history !== null && history.length > 0 && (
              <ul className="space-y-2 text-sm">
                {history.map((entry) => (
                  <li key={entry.id} className="text-charcoal-600">
                    <span className="font-medium text-charcoal">{entry.action.replace('mentorship.', '').replace(/_/g, ' ')}</span>
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
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Review status</p>
            <div className="mt-3 space-y-2">
              {APPLICATION_STATUSES.filter((s) => s !== application.status).map((s) => (
                <button key={s} type="button" onClick={() => applyStatus(s)} className="btn-secondary w-full !py-2 text-xs capitalize">
                  Mark {s}
                </button>
              ))}
            </div>
            {application.reviewedBy && <p className="mt-3 text-xs text-charcoal-600/60">Last reviewed by {application.reviewedBy}</p>}
          </div>

          <Link to={application.role === 'mentor' ? '/admin/mentorship/mentors' : '/admin/mentorship/mentees'} className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all {application.role === 'mentor' ? 'mentors' : 'mentees'}
          </Link>
        </div>
      </div>

      {confirmAction?.type === 'delete' && (
        <ConfirmDialog
          title="Delete this application?"
          description="This permanently removes the record. Only Submitted, Reviewing, Declined, or Withdrawn applications without notes can be deleted."
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
