import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Plus, X } from 'lucide-react'
import { fetchMatches, fetchApplications, fetchPrograms, createMatch } from '../../api/mentorship'
import { MATCH_STATUSES } from '../../constants/mentorship'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

function CompatibilityView({ mentor, mentee }) {
  if (!mentor || !mentee) return null
  const mentorTopics = new Set(mentor.topicSlugs)
  const shared = mentee.topics.filter((t) => mentorTopics.has(t.slug)).map((t) => t.name)
  const stageMatch = (mentor.careerStagesSupported || []).includes(mentee.careerStage)
  const timezoneNote = mentor.timezone && mentee.timezone
    ? (mentor.timezone === mentee.timezone ? 'Same timezone' : `${mentor.timezone} vs ${mentee.timezone}`)
    : 'Not specified by one or both'

  return (
    <div className="mt-4 border border-dashed border-taupe-300 bg-taupe-50 p-4 text-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Compatibility (informational only — final decision is yours)</p>
      <dl className="mt-2 space-y-1">
        <div className="flex justify-between"><dt className="text-charcoal-600">Shared topics</dt><dd className="text-charcoal">{shared.length ? shared.join(', ') : 'None'}</dd></div>
        <div className="flex justify-between"><dt className="text-charcoal-600">Mentor industry</dt><dd className="text-charcoal">{mentor.industry || '—'}</dd></div>
        <div className="flex justify-between"><dt className="text-charcoal-600">Mentee career stage fit</dt><dd className="text-charcoal">{stageMatch ? 'Supported by mentor' : 'Not listed by mentor'}</dd></div>
        <div className="flex justify-between"><dt className="text-charcoal-600">Timezone</dt><dd className="text-charcoal">{timezoneNote}</dd></div>
        <div className="flex justify-between"><dt className="text-charcoal-600">Mentor capacity</dt><dd className="text-charcoal">{mentor.activeMenteeCount}{mentor.mentorCapacity ? ` / ${mentor.mentorCapacity}` : ' (no stated limit)'}</dd></div>
      </dl>
    </div>
  )
}

export default function AdminMentorshipMatches() {
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)
  const [status, setStatus] = useState('')
  const [programId, setProgramId] = useState('')
  const [programs, setPrograms] = useState([])

  const [showCreate, setShowCreate] = useState(false)
  const [mentors, setMentors] = useState([])
  const [mentees, setMentees] = useState([])
  const [mentorId, setMentorId] = useState('')
  const [menteeId, setMenteeId] = useState('')
  const [plannedStartDate, setPlannedStartDate] = useState('')
  const [plannedEndDate, setPlannedEndDate] = useState('')
  const [matchingNotes, setMatchingNotes] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    fetchPrograms({ pageSize: 100 }).then((res) => setPrograms(res.items)).catch(() => {})
  }, [])

  function load() {
    let active = true
    setError(null)
    fetchMatches({ status: status || undefined, programId: programId || undefined, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading matches. Please try again.'))
    return () => {
      active = false
    }
  }

  useEffect(load, [status, programId]) // eslint-disable-line react-hooks/exhaustive-deps

  function openCreate() {
    setShowCreate(true)
    fetchApplications({ role: 'mentor', status: 'approved', pageSize: 200 }).then((res) => setMentors(res.items))
    fetchApplications({ role: 'mentee', status: 'approved', pageSize: 200 }).then((res) => setMentees(res.items))
  }

  const selectedMentor = mentors.find((m) => String(m.id) === mentorId)
  const selectedMentee = mentees.find((m) => String(m.id) === menteeId)

  async function handleCreate() {
    if (!mentorId || !menteeId) {
      toast.error('Select both a mentor and a mentee.')
      return
    }
    setCreating(true)
    try {
      const match = await createMatch({ mentorApplicationId: mentorId, menteeApplicationId: menteeId, plannedStartDate, plannedEndDate, matchingNotes })
      toast.success('Match created as Proposed.')
      if (match.capacityWarning) toast.warn(match.capacityWarning)
      setShowCreate(false)
      setMentorId('')
      setMenteeId('')
      setPlannedStartDate('')
      setPlannedEndDate('')
      setMatchingNotes('')
      load()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong creating this match.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Matches"
        description="Pair approved mentors and mentees, and track active mentorship relationships."
        actions={
          <button type="button" onClick={openCreate} className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New match
          </button>
        }
      />

      {showCreate && (
        <div className="mb-6 border border-taupe-300 bg-white p-6">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Create a match</p>
            <button type="button" onClick={() => setShowCreate(false)} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Close">
              <X size={16} />
            </button>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Mentor</label>
              <select value={mentorId} onChange={(e) => setMentorId(e.target.value)} className={`${inputClass} mt-1.5`}>
                <option value="">Select an approved mentor…</option>
                {mentors.map((m) => (
                  <option key={m.id} value={m.id}>{m.fullName} — {m.professionalTitle || m.industry || 'no title'}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Mentee</label>
              <select value={menteeId} onChange={(e) => setMenteeId(e.target.value)} className={`${inputClass} mt-1.5`}>
                <option value="">Select an approved mentee…</option>
                {mentees.map((m) => (
                  <option key={m.id} value={m.id}>{m.fullName} — {m.careerStage || 'stage not set'}</option>
                ))}
              </select>
            </div>
          </div>

          <CompatibilityView mentor={selectedMentor} mentee={selectedMentee} />

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Planned start</label>
              <input type="date" value={plannedStartDate} onChange={(e) => setPlannedStartDate(e.target.value)} className={`${inputClass} mt-1.5`} />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Planned end</label>
              <input type="date" value={plannedEndDate} onChange={(e) => setPlannedEndDate(e.target.value)} className={`${inputClass} mt-1.5`} />
            </div>
          </div>
          <div className="mt-4">
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Matching notes</label>
            <textarea rows={2} value={matchingNotes} onChange={(e) => setMatchingNotes(e.target.value)} placeholder="Why this pairing makes sense…" className={`${inputClass} mt-1.5`} />
          </div>
          <button type="button" onClick={handleCreate} disabled={creating} className="btn-primary mt-4 !px-4 !py-2 text-xs disabled:opacity-60">
            {creating ? 'Creating…' : 'Create match (Proposed)'}
          </button>
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select value={programId} onChange={(e) => setProgramId(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All programs</option>
          {programs.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {MATCH_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load matches" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Program</th>
                  <th className="px-4 py-3">Mentor</th>
                  <th className="px-4 py-3">Mentee</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Matched</th>
                  <th className="px-4 py-3">Start</th>
                  <th className="px-4 py-3">End</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 text-charcoal-600">{row.program?.name || '—'}</td>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/mentorship/matches/${row.id}`} className="hover:text-burgundy-600">{row.mentorApplication?.fullName}</Link>
                    </td>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/mentorship/matches/${row.id}`} className="hover:text-burgundy-600">{row.menteeApplication?.fullName}</Link>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.matchedAt ? formatDate(row.matchedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.plannedStartDate ? formatDate(row.plannedStartDate) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.plannedEndDate ? formatDate(row.plannedEndDate) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No matches yet" description="Approve a mentor and a mentee, then create your first match." />
        )
      )}
    </div>
  )
}
