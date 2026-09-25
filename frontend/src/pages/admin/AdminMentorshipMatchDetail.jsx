import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import {
  fetchMatch, updateMatch, updateMatchStatus, addMatchNote, fetchMatchHistory, addMatchSession, updateMatchSession,
} from '../../api/mentorship'
import { MATCH_STATUSES, SESSION_STATUSES } from '../../constants/mentorship'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import { formatDate } from '../../utils/format'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

export default function AdminMentorshipMatchDetail() {
  const { id } = useParams()

  const [match, setMatch] = useState(undefined)
  const [form, setForm] = useState(null)
  const [history, setHistory] = useState(null)
  const [noteBody, setNoteBody] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [closureReason, setClosureReason] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  const [sessionDate, setSessionDate] = useState('')
  const [sessionSummary, setSessionSummary] = useState('')
  const [addingSession, setAddingSession] = useState(false)

  function load() {
    let active = true
    Promise.all([fetchMatch(id), fetchMatchHistory(id)])
      .then(([m, historyEntries]) => {
        if (!active) return
        if (!m) {
          setNotFound(true)
          return
        }
        setMatch(m)
        setForm({ plannedStartDate: m.plannedStartDate, plannedEndDate: m.plannedEndDate })
        setHistory(historyEntries)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this match. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSaveDates() {
    setSaving(true)
    try {
      const updated = await updateMatch(id, form)
      setMatch(updated)
      toast.success('Match updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this match.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateMatchStatus(id, status, closureReason || undefined)
      setMatch(updated)
      toast.success(`Match marked ${status.replace(/_/g, ' ')}.`)
      fetchMatchHistory(id).then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
      setClosureReason('')
    }
  }

  function handleStatusClick(status) {
    if (['completed', 'cancelled', 'rematch_needed'].includes(status)) {
      setClosureReason('')
      setConfirmAction({ status })
    } else {
      applyStatus(status)
    }
  }

  async function handleAddNote() {
    if (!noteBody.trim()) return
    try {
      const updated = await addMatchNote(id, noteBody.trim())
      setMatch(updated)
      setNoteBody('')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this note.')
    }
  }

  async function handleAddSession() {
    if (!sessionDate) {
      toast.error('Session date is required.')
      return
    }
    setAddingSession(true)
    try {
      const updated = await addMatchSession(id, { sessionDate, summary: sessionSummary })
      setMatch(updated)
      setSessionDate('')
      setSessionSummary('')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this session.')
    } finally {
      setAddingSession(false)
    }
  }

  async function handleSessionStatusChange(sessionId, status) {
    try {
      const updated = await updateMatchSession(id, sessionId, { status })
      setMatch(updated)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating this session.')
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this match" description={loadError} />
  if (notFound) return <EmptyState title="Match not found" description="This match may have been removed or the URL is incorrect." />
  if (match === undefined || form === null) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={`${match.mentorApplication?.fullName} × ${match.menteeApplication?.fullName}`}
        description={`${match.program?.name || 'Mentorship match'} — private, internal record.`}
        actions={<StatusBadge status={match.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-6">
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Pairing</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="border border-taupe-200 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">Mentor</p>
                <p className="mt-1 text-sm font-medium text-charcoal">{match.mentorApplication?.fullName}</p>
                <p className="text-xs text-charcoal-600">{match.mentorApplication?.professionalTitle} {match.mentorApplication?.organizationName ? `at ${match.mentorApplication.organizationName}` : ''}</p>
              </div>
              <div className="border border-taupe-200 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">Mentee</p>
                <p className="mt-1 text-sm font-medium text-charcoal">{match.menteeApplication?.fullName}</p>
                <p className="text-xs text-charcoal-600">{match.menteeApplication?.professionalTitle} {match.menteeApplication?.organizationName ? `at ${match.menteeApplication.organizationName}` : ''}</p>
              </div>
            </div>
            {match.matchingNotes && (
              <div className="mt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Matching rationale</p>
                <p className="mt-1 text-sm text-charcoal-600">{match.matchingNotes}</p>
              </div>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Timeline</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Planned start</label>
                <input type="date" value={form.plannedStartDate || ''} onChange={(e) => setForm({ ...form, plannedStartDate: e.target.value })} className={`${inputClass} mt-1.5`} />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Planned end</label>
                <input type="date" value={form.plannedEndDate || ''} onChange={(e) => setForm({ ...form, plannedEndDate: e.target.value })} className={`${inputClass} mt-1.5`} />
              </div>
            </div>
            <button type="button" onClick={handleSaveDates} disabled={saving} className="btn-secondary mt-3 !px-4 !py-2 text-xs disabled:opacity-60">
              {saving ? 'Saving…' : 'Save dates'}
            </button>
            {match.actualCompletionDate && (
              <p className="mt-3 text-xs text-charcoal-600">Actual completion: {formatDate(match.actualCompletionDate)}</p>
            )}
            {match.closureReason && <p className="mt-1 text-xs text-charcoal-600">Closure reason: {match.closureReason}</p>}
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Check-ins</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Lightweight internal records — never shown publicly.</p>
            <div className="space-y-2">
              {match.sessions.length === 0 && <p className="text-sm text-charcoal-600/60">No check-ins recorded yet.</p>}
              {match.sessions.map((s) => (
                <div key={s.id} className="border border-taupe-200 px-3 py-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-charcoal">{formatDate(s.sessionDate)}</span>
                    <select value={s.status} onChange={(e) => handleSessionStatusChange(s.id, e.target.value)} className="border border-taupe-300 px-2 py-1 text-xs">
                      {SESSION_STATUSES.map((st) => (
                        <option key={st} value={st}>{st}</option>
                      ))}
                    </select>
                  </div>
                  {s.summary && <p className="mt-1 text-charcoal-600">{s.summary}</p>}
                </div>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[160px_1fr_auto]">
              <input type="date" value={sessionDate} onChange={(e) => setSessionDate(e.target.value)} className={inputClass} />
              <input value={sessionSummary} onChange={(e) => setSessionSummary(e.target.value)} placeholder="Short summary (optional)" className={inputClass} />
              <button type="button" onClick={handleAddSession} disabled={addingSession} className="btn-secondary !px-3 !py-2 text-xs disabled:opacity-60">
                Add check-in
              </button>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <div className="space-y-2">
              {match.notes.length === 0 && <p className="text-sm text-charcoal-600/60">No notes yet.</p>}
              {match.notes.map((n) => (
                <div key={n.id} className="border border-taupe-200 px-3 py-2 text-sm">
                  <p className="text-charcoal">{n.body}</p>
                  <p className="mt-1 text-xs text-charcoal-600/60">{n.user || 'Staff'} &middot; {n.createdAt ? formatDate(n.createdAt) : ''}</p>
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
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Status</p>
            <div className="mt-3 space-y-2">
              {MATCH_STATUSES.filter((s) => s !== match.status).map((s) => (
                <button key={s} type="button" onClick={() => handleStatusClick(s)} className="btn-secondary w-full !py-2 text-xs capitalize">
                  Mark {s.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          <Link to="/admin/mentorship/matches" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all matches
          </Link>
        </div>
      </div>

      {confirmAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/70 p-4" role="alertdialog" aria-modal="true">
          <div className="w-full max-w-sm bg-ivory p-6 shadow-card">
            <h3 className="font-serif text-lg font-semibold text-charcoal">Mark as {confirmAction.status.replace(/_/g, ' ')}?</h3>
            <p className="mt-2 text-sm text-charcoal-600">This match's history is preserved either way.</p>
            <textarea
              rows={2}
              value={closureReason}
              onChange={(e) => setClosureReason(e.target.value)}
              placeholder="Reason (optional)"
              className="mt-3 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
            />
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setConfirmAction(null)
                  setClosureReason('')
                }}
                className="btn-secondary !px-4 !py-2 text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => applyStatus(confirmAction.status)}
                className={`!px-4 !py-2 text-xs font-semibold text-ivory ${confirmAction.status === 'cancelled' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-burgundy-500 hover:bg-burgundy-600'}`}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
