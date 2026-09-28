import { useState } from 'react'
import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'
import { CalendarClock, CheckCircle2, Send, Undo2, XCircle, Archive as ArchiveIcon } from 'lucide-react'
import StatusBadge from './StatusBadge'
import ConfirmDialog from './ConfirmDialog'
import { formatDate } from '../../utils/format'

/**
 * The editorial workflow action panel for AdminArticleEditor — shows the
 * current status, the effective publication/schedule time, and only the
 * actions that are actually valid from the article's current status (see
 * app/services/articles_workflow.py's WORKFLOW_TRANSITIONS on the
 * backend, which this mirrors but never substitutes for: every action
 * here still round-trips through the real backend endpoint, which is the
 * actual source of truth/enforcement — see spec: "Do not trust frontend
 * state.").
 *
 * `status`/`scheduledAt`/`publishedAt`/`approvedAt`/`approvedByName` come
 * from the freshest loaded article. Every action prop is an async
 * function; this panel handles its own busy/disabled state and surfaces
 * failures via the `onError` callback (a toast in the parent) rather than
 * silently reverting anything.
 */
export default function ArticleWorkflowPanel({
  status,
  scheduledAt,
  publishedAt,
  approvedAt,
  approvedByName,
  onSubmitReview,
  onRequestChanges,
  onMoveToDraft,
  onApprove,
  onSchedule,
  onReschedule,
  onUnschedule,
  onPublishNow,
  onArchive,
  onError,
}) {
  const [busy, setBusy] = useState(false)
  const [scheduleDraft, setScheduleDraft] = useState(scheduledAt ? new Date(scheduledAt) : null)
  const [showScheduler, setShowScheduler] = useState(false)
  const [changesNote, setChangesNote] = useState('')
  const [showChangesNote, setShowChangesNote] = useState(false)
  const [confirming, setConfirming] = useState(null) // 'publish' | 'unschedule' | 'archive' | null

  async function run(action, ...args) {
    setBusy(true)
    try {
      await action(...args)
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'That action failed. Please try again.'
      onError?.(message)
    } finally {
      setBusy(false)
    }
  }

  function submitSchedule() {
    if (!scheduleDraft) return
    const iso = scheduleDraft.toISOString()
    run(status === 'scheduled' ? onReschedule : onSchedule, iso).then(() => setShowScheduler(false))
  }

  return (
    <div className="border border-taupe-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Status</p>
        <StatusBadge status={status} />
      </div>

      <dl className="mt-3 space-y-1 text-xs text-charcoal-600">
        {status === 'published' && publishedAt && (
          <div className="flex justify-between">
            <dt>Published</dt>
            <dd>{formatDate(publishedAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}</dd>
          </div>
        )}
        {status === 'scheduled' && scheduledAt && (
          <div className="flex justify-between">
            <dt>Scheduled</dt>
            <dd>{formatDate(scheduledAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })} (your local time)</dd>
          </div>
        )}
        {approvedAt && (
          <div className="flex justify-between">
            <dt>Approved</dt>
            <dd>
              {formatDate(approvedAt, { month: 'short', day: 'numeric', year: 'numeric' })}
              {approvedByName ? ` — ${approvedByName}` : ''}
            </dd>
          </div>
        )}
      </dl>

      <div className="mt-4 space-y-2">
        {status === 'draft' && (
          <button type="button" disabled={busy} onClick={() => run(onSubmitReview)} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
            <Send size={13} /> Submit for review
          </button>
        )}

        {status === 'in_review' && (
          <>
            <button type="button" disabled={busy} onClick={() => run(onApprove)} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
              <CheckCircle2 size={13} /> Approve
            </button>
            {!showChangesNote ? (
              <button type="button" disabled={busy} onClick={() => setShowChangesNote(true)} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                <XCircle size={13} /> Request changes
              </button>
            ) : (
              <div className="space-y-2 border border-taupe-200 p-2">
                <textarea
                  rows={2}
                  value={changesNote}
                  onChange={(e) => setChangesNote(e.target.value)}
                  placeholder="What needs to change? (optional, visible in the Audit Log)"
                  className="w-full border border-taupe-300 px-2 py-1.5 text-xs focus:border-burgundy-500 focus:outline-none"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => run(onRequestChanges, changesNote || undefined).then(() => setShowChangesNote(false))}
                    className="btn-primary flex-1 !py-1.5 text-xs disabled:opacity-60"
                  >
                    Send back
                  </button>
                  <button type="button" onClick={() => setShowChangesNote(false)} className="btn-secondary flex-1 !py-1.5 text-xs">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {status === 'changes_requested' && (
          <>
            <button type="button" disabled={busy} onClick={() => run(onMoveToDraft)} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
              <Undo2 size={13} /> Move to draft
            </button>
            <button type="button" disabled={busy} onClick={() => run(onSubmitReview)} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
              <Send size={13} /> Resubmit for review
            </button>
          </>
        )}

        {(status === 'approved' || status === 'scheduled') && !showScheduler && (
          <button type="button" disabled={busy} onClick={() => setShowScheduler(true)} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
            <CalendarClock size={13} /> {status === 'scheduled' ? 'Reschedule' : 'Schedule'}
          </button>
        )}

        {showScheduler && (
          <div className="space-y-2 border border-taupe-200 p-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">
              Publication date &amp; time <span className="normal-case text-charcoal-600/60">— your local timezone; stored as UTC</span>
            </label>
            <DatePicker
              selected={scheduleDraft}
              onChange={setScheduleDraft}
              showTimeSelect
              minDate={new Date()}
              dateFormat="MMM d, yyyy h:mm aa"
              placeholderText="Pick a future date and time"
              className="w-full border border-taupe-300 px-2 py-1.5 text-xs focus:border-burgundy-500 focus:outline-none"
            />
            <div className="flex gap-2">
              <button type="button" disabled={busy || !scheduleDraft} onClick={submitSchedule} className="btn-primary flex-1 !py-1.5 text-xs disabled:opacity-60">
                Confirm
              </button>
              <button type="button" onClick={() => setShowScheduler(false)} className="btn-secondary flex-1 !py-1.5 text-xs">
                Cancel
              </button>
            </div>
          </div>
        )}

        {status === 'scheduled' && !showScheduler && (
          <button type="button" disabled={busy} onClick={() => setConfirming('unschedule')} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
            Unschedule
          </button>
        )}

        {(status === 'approved' || status === 'scheduled') && !showScheduler && (
          <button type="button" disabled={busy} onClick={() => setConfirming('publish')} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
            Publish now
          </button>
        )}

        {status === 'published' && (
          <button type="button" disabled={busy} onClick={() => setConfirming('archive')} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
            <ArchiveIcon size={13} /> Archive
          </button>
        )}

        {status === 'archived' && <p className="text-xs text-charcoal-600/70">Archived articles are no longer publicly visible. This is a terminal state.</p>}
      </div>

      {confirming === 'publish' && (
        <ConfirmDialog
          title="Publish this article now?"
          description="It will immediately become publicly visible at its flat URL, replacing any existing schedule."
          confirmLabel="Publish now"
          danger={false}
          onConfirm={() => {
            setConfirming(null)
            run(onPublishNow)
          }}
          onCancel={() => setConfirming(null)}
        />
      )}
      {confirming === 'unschedule' && (
        <ConfirmDialog
          title="Unschedule this article?"
          description="It returns to Approved and will not publish automatically until scheduled again."
          confirmLabel="Unschedule"
          onConfirm={() => {
            setConfirming(null)
            run(onUnschedule)
          }}
          onCancel={() => setConfirming(null)}
        />
      )}
      {confirming === 'archive' && (
        <ConfirmDialog
          title="Archive this article?"
          description="It will be removed from public pages, search, and listings. Its record and history are kept, and this can't be undone from here."
          confirmLabel="Archive"
          onConfirm={() => {
            setConfirming(null)
            run(onArchive)
          }}
          onCancel={() => setConfirming(null)}
        />
      )}
    </div>
  )
}
