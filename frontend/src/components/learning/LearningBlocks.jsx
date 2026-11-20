import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, CheckCircle2, Lightbulb, ListChecks, MessageCircleQuestion, NotebookPen, Sparkles, XCircle } from 'lucide-react'
import { checkKnowledgeAnswers } from '../../api/learning'
import { isInternalPath, safeLinkUrl } from '../../utils/linkSafety'

// Text-first lesson elements (sanitized server-side — see backend
// content_blocks.LEARNING_BLOCK_SANITIZERS). Rendered through
// ArticleContent's `extraRenderers`, so lessons reuse every normal block
// (paragraphs, lists with continued numbering, quotes, images…) as-is.

function Html({ as: Tag = 'span', html, className }) {
  if (!html) return null
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />
}

const panel = 'my-8 rounded-card border p-5 sm:p-6'
const LINKS = '[&_a]:text-burgundy-600 [&_a]:underline [&_a]:underline-offset-2'

// Private, device-local notes (reflection answers, checklist ticks): never
// sent to WSF. Storage can be unavailable (private mode) — then the UI still
// works for the visit, it just won't remember.
function useLocalState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = key ? window.localStorage.getItem(key) : null
      return raw === null ? initial : JSON.parse(raw)
    } catch {
      return initial
    }
  })
  function update(next) {
    setValue(next)
    try {
      if (key) window.localStorage.setItem(key, JSON.stringify(next))
    } catch {
      /* storage unavailable: keep in memory only */
    }
  }
  return [value, update]
}

function BlockHeading({ icon: Icon, children, id }) {
  return (
    <p id={id} className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">
      <Icon size={16} aria-hidden="true" /> {children}
    </p>
  )
}

export function KeyTakeaways({ block }) {
  const items = block.items || []
  if (!items.length) return null
  return (
    <aside className={`${panel} border-taupe-200 bg-cream`} aria-label={block.title || 'Key takeaways'}>
      <BlockHeading icon={Sparkles}>{block.title || 'Key takeaways'}</BlockHeading>
      <ul className={`mt-3 space-y-2 pl-5 text-[1.0625rem] leading-relaxed text-charcoal marker:text-burgundy-500 list-disc ${LINKS}`}>
        {items.map((item, i) => (
          <Html key={i} as="li" html={item} />
        ))}
      </ul>
    </aside>
  )
}

export function TryThis({ block }) {
  if (!block.text) return null
  return (
    <aside className={`${panel} border-l-4 border-taupe-200 border-l-plum-600 bg-blush-50`} aria-label={block.title || 'Try this'}>
      <BlockHeading icon={Lightbulb}>{block.title || 'Try this'}</BlockHeading>
      <Html as="p" html={block.text} className={`mt-2 text-[1.0625rem] leading-relaxed text-charcoal ${LINKS}`} />
    </aside>
  )
}

export function Reflection({ block, lessonId, blockIndex }) {
  const prompts = block.prompts || []
  const [answers, setAnswers] = useLocalState(lessonId ? `wsf-reflection:${lessonId}:${blockIndex}` : null, {})
  const baseId = useId()
  if (!prompts.length) return null
  return (
    <section className={`${panel} border-taupe-200 bg-white`} aria-labelledby={`${baseId}-h`}>
      <BlockHeading icon={NotebookPen} id={`${baseId}-h`}>{block.title || 'Reflection'}</BlockHeading>
      <p className="mt-1 text-sm text-charcoal-600">Your answers stay private on this device.</p>
      <div className="mt-4 space-y-4">
        {prompts.map((prompt, i) => (
          <div key={i}>
            <label htmlFor={`${baseId}-${i}`} className="block text-[1.0625rem] font-medium leading-snug text-charcoal">
              {prompt}
            </label>
            <textarea
              id={`${baseId}-${i}`}
              rows={3}
              value={answers[i] || ''}
              onChange={(e) => setAnswers({ ...answers, [i]: e.target.value })}
              className="mt-2 w-full rounded-control border border-taupe-300 px-3 py-2 text-base text-charcoal focus:border-burgundy-500 focus:outline-none"
            />
          </div>
        ))}
      </div>
    </section>
  )
}

export function CaseStudy({ block }) {
  if (!block.text && !block.title) return null
  return (
    <section className={`${panel} border-taupe-200 bg-white`} aria-label={block.title || 'Case study'}>
      <BlockHeading icon={BookOpen}>Case study</BlockHeading>
      {block.title && <h3 className="mt-2 font-serif text-xl font-semibold text-charcoal">{block.title}</h3>}
      <Html as="div" html={block.text} className={`mt-2 text-[1.0625rem] leading-relaxed text-charcoal ${LINKS}`} />
      {block.questions?.length > 0 && (
        <div className="mt-4 border-t border-taupe-200 pt-4">
          <p className="text-sm font-semibold text-charcoal">Think about it</p>
          <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-[1.0625rem] text-charcoal-600">
            {block.questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}

export function Checklist({ block, lessonId, blockIndex }) {
  const items = block.items || []
  const [checked, setChecked] = useLocalState(lessonId ? `wsf-checklist:${lessonId}:${blockIndex}` : null, {})
  const baseId = useId()
  if (!items.length) return null
  const done = items.filter((_, i) => checked[i]).length
  return (
    <section className={`${panel} border-taupe-200 bg-white`} aria-labelledby={`${baseId}-h`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <BlockHeading icon={ListChecks} id={`${baseId}-h`}>{block.title || 'Checklist'}</BlockHeading>
        <p className="text-sm text-charcoal-600" aria-live="polite">
          {done} of {items.length} done
        </p>
      </div>
      <ul className="mt-3 space-y-2">
        {items.map((item, i) => (
          <li key={i}>
            <label className="flex cursor-pointer items-start gap-3 text-[1.0625rem] leading-snug text-charcoal">
              <input
                type="checkbox"
                checked={!!checked[i]}
                onChange={(e) => setChecked({ ...checked, [i]: e.target.checked })}
                className="mt-1 h-4 w-4 shrink-0 accent-plum-600"
              />
              <span className={checked[i] ? 'text-charcoal-600 line-through decoration-taupe-400' : ''}>{item}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-charcoal-600/80">Saved on this device only.</p>
    </section>
  )
}

function Question({ question, index, value, onChange, result, disabled, baseId }) {
  const multiple = question.kind === 'multiple'
  const name = `${baseId}-q${index}`
  return (
    <fieldset className="mt-5 first:mt-3">
      <legend className="text-[1.0625rem] font-medium leading-snug text-charcoal">
        <span className="mr-1 text-charcoal-600">{index + 1}.</span> {question.prompt}
        {multiple && <span className="ml-1 text-sm font-normal text-charcoal-600">(choose all that apply)</span>}
      </legend>
      <div className="mt-2 space-y-1.5">
        {question.options.map((option) => {
          const selected = multiple ? (value || []).includes(option.id) : (value || [])[0] === option.id
          const isCorrect = result?.correctOptionIds?.includes(option.id)
          return (
            <label
              key={option.id}
              className={`flex cursor-pointer items-start gap-3 rounded-control border px-3 py-2 text-base ${
                result && isCorrect ? 'border-emerald-600 bg-emerald-50' : 'border-taupe-200 bg-white hover:border-taupe-400'
              }`}
            >
              <input
                type={multiple ? 'checkbox' : 'radio'}
                name={name}
                checked={selected}
                disabled={disabled}
                onChange={(e) => {
                  if (multiple) onChange(e.target.checked ? [...(value || []), option.id] : (value || []).filter((v) => v !== option.id))
                  else onChange([option.id])
                }}
                className="mt-1 h-4 w-4 shrink-0 accent-plum-600"
              />
              <span className="text-charcoal">
                {option.text}
                {result && isCorrect && <span className="ml-2 text-sm font-semibold text-emerald-700">Correct answer</span>}
              </span>
            </label>
          )
        })}
      </div>
      {result && (
        <div className="mt-2 flex items-start gap-2 text-sm" role="status">
          {result.correct ? (
            <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-700" aria-hidden="true" />
          ) : (
            <XCircle size={18} className="mt-0.5 shrink-0 text-burgundy-600" aria-hidden="true" />
          )}
          <p className="text-charcoal">
            <span className="font-semibold">{result.correct ? 'Correct.' : 'Not quite.'}</span> {result.explanation}
          </p>
        </div>
      )}
    </fieldset>
  )
}

// 2–5 lightweight questions with immediate feedback from the server
// (answers are never sent to the browser in advance). Never blocks
// progress, and nothing is recorded.
export function KnowledgeCheck({ block, lessonId }) {
  const questions = block.questions || []
  const [answers, setAnswers] = useState({})
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const baseId = useId()
  if (!questions.length) return null
  const answeredAll = questions.every((q) => (answers[q.id] || []).length > 0)
  const byId = Object.fromEntries((results || []).map((r) => [r.questionId, r]))
  const correctCount = (results || []).filter((r) => r.correct).length

  async function check() {
    setBusy(true)
    setError(null)
    try {
      setResults(await checkKnowledgeAnswers(lessonId, answers))
    } catch {
      setError('We couldn’t check your answers just now. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={`${panel} border-taupe-300 bg-ivory`} aria-labelledby={`${baseId}-h`}>
      <BlockHeading icon={MessageCircleQuestion} id={`${baseId}-h`}>{block.title || 'Knowledge check'}</BlockHeading>
      <p className="mt-1 text-sm text-charcoal-600">A quick check for yourself. It doesn&apos;t affect your progress.</p>
      {questions.map((question, i) => (
        <Question
          key={question.id}
          baseId={baseId}
          question={question}
          index={i}
          value={answers[question.id]}
          onChange={(v) => setAnswers({ ...answers, [question.id]: v })}
          result={byId[question.id]}
          disabled={!!results}
        />
      ))}
      {error && <p className="mt-3 text-sm text-burgundy-600" role="alert">{error}</p>}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        {results ? (
          <>
            <p className="text-sm font-semibold text-charcoal" role="status">
              {correctCount} of {questions.length} correct
            </p>
            <button type="button" onClick={() => { setResults(null); setAnswers({}) }} className="btn-secondary !px-4 !py-2">
              Try again
            </button>
          </>
        ) : (
          <button type="button" onClick={check} disabled={!answeredAll || busy || !lessonId} className="btn-primary !px-5 !py-2.5 disabled:opacity-50">
            {busy ? 'Checking…' : 'Check answers'}
          </button>
        )}
      </div>
    </section>
  )
}

export function ResourceLink({ block }) {
  if (!block.resourceSlug) return null
  return (
    <aside className={`${panel} flex items-start gap-4 border-taupe-200 bg-cream`}>
      <span className="mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-burgundy-600">
        <NotebookPen size={18} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">Worksheet</p>
        <Link to={`/resources/${block.resourceSlug}`} className="mt-1 block font-serif text-lg font-semibold text-charcoal hover:text-burgundy-600">
          {block.label || 'Open the worksheet'}
        </Link>
        {block.note && <p className="mt-1 text-sm text-charcoal-600">{block.note}</p>}
      </div>
    </aside>
  )
}

export function FurtherReading({ block }) {
  const links = (block.links || []).map((l) => ({ ...l, url: safeLinkUrl(l.url) })).filter((l) => l.url && l.label)
  if (!links.length) return null
  return (
    <section className="my-8 border-t border-taupe-200 pt-5" aria-label={block.title || 'Further reading'}>
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">{block.title || 'Further reading'}</p>
      <ul className="mt-3 space-y-2">
        {links.map((link, i) => (
          <li key={i}>
            {isInternalPath(link.url) ? (
              <Link to={link.url} className="font-medium text-burgundy-600 hover:underline">{link.label}</Link>
            ) : (
              <a href={link.url} rel="noopener noreferrer" className="font-medium text-burgundy-600 hover:underline">{link.label}</a>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
