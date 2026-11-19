import { useState } from 'react'
import { toast } from 'react-toastify'
import { reviewSubmissionOutcome } from '../../api/submissions'
import { CAREER_OUTCOME_TYPES, labelFor } from '../../constants/workplace'
import { outcomePublicCredit } from '../../utils/careerOutcomes'

const STATUS_LABEL = { none: 'No outcome', pending: 'Awaiting review', approved: 'Published', rejected: 'Not published' }

const input = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

// Career outcome review on a Story Submission. Publishing needs the
// submitter's consent, a type and an editor-written one-line summary
// (never the raw story). Staff may make attribution anonymous, never
// named; the API enforces the same rules.
export default function CareerOutcomeReview({ submission, onUpdated }) {
  const [review, setReview] = useState({
    outcomeType: submission.outcomeType,
    outcomeSummary: submission.outcomeSummary,
    outcomeAttribution: submission.outcomeAttribution,
  })
  const [saving, setSaving] = useState(false)

  if (!submission.outcomeType && submission.outcomeStatus === 'none') return null

  const credit = outcomePublicCredit(review.outcomeAttribution, submission.firstName, submission.lastName)
  const canApprove = submission.outcomePublishConsent && review.outcomeType && review.outcomeSummary?.trim()

  async function save(outcomeStatus, message) {
    setSaving(true)
    try {
      const updated = await reviewSubmissionOutcome(submission.id, { ...review, outcomeStatus })
      onUpdated(updated)
      toast.success(message)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this outcome.')
    } finally {
      setSaving(false)
    }
  }

  const currentStatus = submission.outcomeStatus === 'none' ? 'pending' : submission.outcomeStatus

  return (
    <div className="border border-taupe-200 bg-white p-6">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Career outcome</p>
        <span className="text-xs font-semibold text-charcoal-600">{STATUS_LABEL[submission.outcomeStatus] || submission.outcomeStatus}</span>
      </div>
      <dl className="mb-4 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-charcoal-600/70">Submitted outcome</dt>
          <dd className="text-charcoal">{labelFor(CAREER_OUTCOME_TYPES, submission.outcomeType) || '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-charcoal-600/70">Publish permission</dt>
          <dd className={submission.outcomePublishConsent ? 'text-emerald-700' : 'font-semibold text-rose-600'}>
            {submission.outcomePublishConsent ? 'Given' : 'Not given: this outcome can never be published'}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-charcoal-600/70">Requested credit</dt>
          <dd className="text-charcoal">{submission.outcomeAttribution === 'first_name' ? 'First name and last initial' : 'Anonymous'}</dd>
        </div>
        <div>
          <dt className="text-xs text-charcoal-600/70">Public credit that will appear</dt>
          <dd className="font-semibold text-charcoal">{credit}</dd>
        </div>
      </dl>
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
          aria-label="Public summary"
          className={input}
        />
        <p className="text-xs text-charcoal-600/70">Write a short factual summary from the story above. Do not say or imply WSF caused the outcome.</p>
        {submission.outcomeAttribution === 'first_name' && (
          <label className="flex items-center gap-2 text-sm text-charcoal-600">
            <input
              type="checkbox"
              checked={review.outcomeAttribution === 'anonymous'}
              onChange={(e) => setReview({ ...review, outcomeAttribution: e.target.checked ? 'anonymous' : 'first_name' })}
            />
            Publish anonymously instead (cannot be undone by staff)
          </label>
        )}
        <div className="flex flex-wrap gap-3 pt-1">
          <button type="button" onClick={() => save('approved', 'Career outcome approved and published.')} disabled={saving || !canApprove} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
            Approve and publish
          </button>
          <button type="button" onClick={() => save('rejected', 'Career outcome will not be published.')} disabled={saving} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
            Do not publish
          </button>
          <button type="button" onClick={() => save(currentStatus, 'Career outcome saved.')} disabled={saving} className="text-xs font-semibold text-charcoal-600 hover:text-burgundy-600 disabled:opacity-60">
            Save without changing status
          </button>
        </div>
        {!canApprove && submission.outcomePublishConsent && (
          <p className="text-xs text-amber-700">Add a public summary to approve.</p>
        )}
      </div>
    </div>
  )
}
