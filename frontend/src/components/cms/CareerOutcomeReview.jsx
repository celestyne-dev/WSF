import { useState } from 'react'
import { toast } from 'react-toastify'
import { reviewSubmissionOutcome } from '../../api/submissions'
import { CAREER_OUTCOME_TYPES, labelFor } from '../../constants/workplace'

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending review' },
  { value: 'approved', label: 'Approved (public)' },
  { value: 'rejected', label: 'Not published' },
]

const input = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

// Career outcome review on a Story Submission. Publishing needs the
// submitter's consent, a type and an editor-written one-line summary
// (never the raw story). Staff may make attribution anonymous, never named.
export default function CareerOutcomeReview({ submission, onUpdated }) {
  const [review, setReview] = useState({
    outcomeType: submission.outcomeType,
    outcomeStatus: submission.outcomeStatus === 'none' ? 'pending' : submission.outcomeStatus,
    outcomeSummary: submission.outcomeSummary,
    outcomeAttribution: submission.outcomeAttribution,
  })
  const [saving, setSaving] = useState(false)

  if (!submission.outcomeType && submission.outcomeStatus === 'none') return null

  async function save() {
    setSaving(true)
    try {
      const updated = await reviewSubmissionOutcome(submission.id, review)
      onUpdated(updated)
      toast.success('Career outcome updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this outcome.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border border-taupe-200 bg-white p-6">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Career outcome</p>
      <p className="mb-4 text-xs text-charcoal-600/80">
        Submitted: {labelFor(CAREER_OUTCOME_TYPES, submission.outcomeType) || '—'} · Publish permission:{' '}
        <span className="font-semibold">{submission.outcomePublishConsent ? 'Yes' : 'No'}</span> · Attribution:{' '}
        {submission.outcomeAttribution === 'first_name' ? 'First name and initial' : 'Anonymous'}
      </p>
      <div className="space-y-3">
        <select value={review.outcomeType} onChange={(e) => setReview({ ...review, outcomeType: e.target.value })} className={input} aria-label="Outcome type">
          {CAREER_OUTCOME_TYPES.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <input
          value={review.outcomeSummary}
          onChange={(e) => setReview({ ...review, outcomeSummary: e.target.value })}
          maxLength={280}
          placeholder="Public one-line summary, e.g. “Promoted to engineering manager.”"
          className={input}
        />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <select value={review.outcomeStatus} onChange={(e) => setReview({ ...review, outcomeStatus: e.target.value })} className={input} aria-label="Outcome status">
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value} disabled={o.value === 'approved' && !submission.outcomePublishConsent}>
                {o.label}
              </option>
            ))}
          </select>
          {submission.outcomeAttribution === 'first_name' && (
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input
                type="checkbox"
                checked={review.outcomeAttribution === 'anonymous'}
                onChange={(e) => setReview({ ...review, outcomeAttribution: e.target.checked ? 'anonymous' : 'first_name' })}
              />
              Publish anonymously instead
            </label>
          )}
        </div>
        <button type="button" onClick={save} disabled={saving} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
          Save outcome review
        </button>
      </div>
    </div>
  )
}
