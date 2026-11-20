import { useId, useState } from 'react'
import { toast } from 'react-toastify'
import { ClipboardCheck } from 'lucide-react'
import { fetchFinalAssessment, submitFinalAssessment } from '../../api/learningEnrollments'

// The optional end-of-course assessment. Questions arrive without answers;
// the server grades, keeps the learner's best score and — when the course
// requires it — completes the course (and issues its certificate) on a pass.
// Feedback is right/wrong per question plus the score; correct answers are
// never revealed, so a retake is a real retake.
export default function FinalAssessment({ enrollment, onEnrollmentChange }) {
  const summary = enrollment?.finalAssessment
  const [questions, setQuestions] = useState(null)
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const baseId = useId()
  if (!summary || enrollment.status !== 'active') return null

  async function start() {
    setBusy(true)
    try {
      const data = await fetchFinalAssessment(enrollment.id)
      setQuestions(data.questions || [])
      setAnswers({})
      setResult(null)
    } catch {
      toast.error('We couldn’t load the assessment. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    setBusy(true)
    try {
      const { result: graded, enrollment: updated } = await submitFinalAssessment(enrollment.id, answers)
      setResult(graded)
      onEnrollmentChange?.(updated)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'We couldn’t submit your answers. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const byId = Object.fromEntries((result?.results || []).map((r) => [r.questionId, r]))
  const answeredAll = (questions || []).every((q) => (answers[q.id] || []).length > 0)

  return (
    <section aria-labelledby={`${baseId}-title`} className="rounded-card border border-taupe-200 bg-white p-6 sm:p-7">
      <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">
        <ClipboardCheck size={16} aria-hidden="true" /> Final assessment
      </p>
      <h2 id={`${baseId}-title`} className="mt-2 font-serif text-2xl font-semibold text-charcoal">
        {summary.questionCount} question{summary.questionCount === 1 ? '' : 's'} · pass mark {summary.passingScore}%
      </h2>
      <p className="mt-1 text-sm text-charcoal-600">
        {summary.required ? 'Passing this assessment is part of completing the course.' : 'Optional: check what you’ve learned.'}
        {enrollment.finalAssessmentBestScore != null && ` Your best score: ${enrollment.finalAssessmentBestScore}%.`}
        {enrollment.finalAssessmentPassed && ' Passed.'}
      </p>

      {!questions ? (
        <button type="button" onClick={start} disabled={busy} className="btn-primary mt-5 !py-2.5 disabled:opacity-60">
          {busy ? 'Loading…' : enrollment.finalAssessmentBestScore != null ? 'Retake the assessment' : 'Start the assessment'}
        </button>
      ) : (
        <form
          className="mt-4"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          {questions.map((q, i) => {
            const multiple = q.kind === 'multiple'
            const graded = byId[q.id]
            return (
              <fieldset key={q.id} className="mt-5">
                <legend className="text-[1.0625rem] font-medium text-charcoal">
                  <span className="mr-1 text-charcoal-600">{i + 1}.</span> {q.prompt}
                  {multiple && <span className="ml-1 text-sm font-normal text-charcoal-600">(choose all that apply)</span>}
                </legend>
                <div className="mt-2 space-y-1.5">
                  {q.options.map((o) => {
                    const value = answers[q.id] || []
                    const selected = multiple ? value.includes(o.id) : value[0] === o.id
                    return (
                      <label key={o.id} className="flex cursor-pointer items-start gap-3 rounded-control border border-taupe-200 px-3 py-2 text-base hover:border-taupe-400">
                        <input
                          type={multiple ? 'checkbox' : 'radio'}
                          name={`${baseId}-${q.id}`}
                          checked={selected}
                          disabled={!!result}
                          onChange={(e) =>
                            setAnswers({
                              ...answers,
                              [q.id]: multiple ? (e.target.checked ? [...value, o.id] : value.filter((v) => v !== o.id)) : [o.id],
                            })
                          }
                          className="mt-1 h-4 w-4 shrink-0 accent-plum-600"
                        />
                        <span className="text-charcoal">{o.text}</span>
                      </label>
                    )
                  })}
                </div>
                {graded && (
                  <p className={`mt-2 text-sm font-semibold ${graded.correct ? 'text-emerald-700' : 'text-burgundy-600'}`}>
                    {graded.correct ? '✓ Correct' : '✗ Incorrect'}
                  </p>
                )}
              </fieldset>
            )
          })}
          {result ? (
            <div className="mt-6 rounded-control bg-cream p-4" role="status">
              <p className="font-serif text-xl font-semibold text-charcoal">
                {result.score}% — {result.passed ? 'Passed' : `Not passed yet (pass mark ${result.passingScore}%)`}
              </p>
              {result.completed && <p className="mt-1 text-sm text-charcoal-600">Course complete.</p>}
              {!result.passed && (
                <button type="button" onClick={start} className="btn-secondary mt-3 !py-2">
                  Try again
                </button>
              )}
            </div>
          ) : (
            <button type="submit" disabled={busy || !answeredAll} className="btn-primary mt-6 !py-2.5 disabled:opacity-50">
              {busy ? 'Submitting…' : 'Submit answers'}
            </button>
          )}
        </form>
      )}
    </section>
  )
}
