import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react'

// Shared by the lesson "Knowledge check" block and a course's final
// assessment. Single choice, multiple choice or true/false only — kept
// deliberately simple. The server re-validates everything on save
// (backend content_blocks.sanitize_question).
const KINDS = [
  { value: 'single', label: 'Single choice' },
  { value: 'multiple', label: 'Multiple choice' },
  { value: 'true_false', label: 'True / false' },
]

const input = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

let counter = 0
const newId = (prefix) => `${prefix}${Date.now().toString(36)}${(counter += 1)}`

function blankQuestion() {
  return {
    id: newId('q'),
    prompt: '',
    kind: 'single',
    options: [
      { id: newId('o'), text: '', correct: true },
      { id: newId('o'), text: '', correct: false },
    ],
    explanation: '',
  }
}

function trueFalse(question) {
  const trueCorrect = question.options?.[0]?.id === 'true' ? !!question.options[0].correct : true
  return [
    { id: 'true', text: 'True', correct: trueCorrect },
    { id: 'false', text: 'False', correct: !trueCorrect },
  ]
}

function QuestionEditor({ question, index, total, onChange, onRemove, onMove }) {
  const patch = (fields) => onChange({ ...question, ...fields })
  const kind = question.kind || 'single'
  const options = kind === 'true_false' ? trueFalse(question) : question.options || []

  function setKind(next) {
    if (next === 'true_false') patch({ kind: next, options: trueFalse({ options: [] }) })
    else patch({ kind: next, options: kind === 'true_false' ? blankQuestion().options : options })
  }
  function setCorrect(optionId, checked) {
    const next = options.map((o) => {
      if (kind === 'multiple') return o.id === optionId ? { ...o, correct: checked } : o
      return { ...o, correct: o.id === optionId }
    })
    patch({ options: next })
  }

  return (
    <fieldset className="border border-taupe-200 bg-white p-3">
      <legend className="px-1 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">Question {index + 1}</legend>
      <div className="mb-2 flex items-center justify-end gap-1">
        <button type="button" onClick={() => onMove(-1)} disabled={index === 0} aria-label={`Move question ${index + 1} up`} className="p-1 text-charcoal-600 disabled:opacity-30"><ChevronUp size={14} /></button>
        <button type="button" onClick={() => onMove(1)} disabled={index === total - 1} aria-label={`Move question ${index + 1} down`} className="p-1 text-charcoal-600 disabled:opacity-30"><ChevronDown size={14} /></button>
        <button type="button" onClick={onRemove} aria-label={`Delete question ${index + 1}`} className="p-1 text-charcoal-600 hover:text-rose-600"><Trash2 size={14} /></button>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_170px]">
        <input value={question.prompt || ''} onChange={(e) => patch({ prompt: e.target.value })} maxLength={300} placeholder="Question" aria-label={`Question ${index + 1} text`} className={input} />
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label={`Question ${index + 1} type`} className={input}>
          {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
      </div>
      <p className="mt-2 text-[11px] text-charcoal-600">{kind === 'multiple' ? 'Tick every correct answer.' : 'Choose the one correct answer.'}</p>
      <ul className="mt-1 space-y-1.5">
        {options.map((option, i) => (
          <li key={option.id} className="flex items-center gap-2">
            <input
              type={kind === 'multiple' ? 'checkbox' : 'radio'}
              name={`correct-${question.id}`}
              checked={!!option.correct}
              onChange={(e) => setCorrect(option.id, e.target.checked)}
              aria-label={`Mark option ${i + 1} correct`}
              className="h-4 w-4 accent-plum-600"
            />
            {kind === 'true_false' ? (
              <span className="text-sm text-charcoal">{option.text}</span>
            ) : (
              <>
                <input
                  value={option.text || ''}
                  onChange={(e) => patch({ options: options.map((o) => (o.id === option.id ? { ...o, text: e.target.value } : o)) })}
                  maxLength={200}
                  placeholder={`Option ${i + 1}`}
                  aria-label={`Option ${i + 1}`}
                  className={input}
                />
                <button type="button" onClick={() => patch({ options: options.filter((o) => o.id !== option.id) })} disabled={options.length <= 2} aria-label={`Remove option ${i + 1}`} className="p-1 text-charcoal-600 hover:text-rose-600 disabled:opacity-30">
                  <Trash2 size={14} />
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      {kind !== 'true_false' && options.length < 6 && (
        <button type="button" onClick={() => patch({ options: [...options, { id: newId('o'), text: '', correct: false }] })} className="mt-2 text-xs font-semibold text-burgundy-600">
          + Add option
        </button>
      )}
      <textarea value={question.explanation || ''} onChange={(e) => patch({ explanation: e.target.value })} maxLength={600} rows={2} placeholder="Explanation shown after answering (optional)" aria-label={`Question ${index + 1} explanation`} className={`${input} mt-2`} />
    </fieldset>
  )
}

export default function QuestionListEditor({ questions = [], onChange, max = 5 }) {
  function update(i, next) {
    onChange(questions.map((q, idx) => (idx === i ? next : q)))
  }
  function move(i, dir) {
    const target = i + dir
    if (target < 0 || target >= questions.length) return
    const copy = [...questions]
    ;[copy[i], copy[target]] = [copy[target], copy[i]]
    onChange(copy)
  }
  return (
    <div className="space-y-3">
      {questions.map((q, i) => (
        <QuestionEditor key={q.id || i} question={q} index={i} total={questions.length} onChange={(next) => update(i, next)} onRemove={() => onChange(questions.filter((_, idx) => idx !== i))} onMove={(dir) => move(i, dir)} />
      ))}
      {questions.length < max ? (
        <button type="button" onClick={() => onChange([...questions, blankQuestion()])} className="inline-flex items-center gap-1 text-xs font-semibold text-burgundy-600">
          <Plus size={13} aria-hidden="true" /> Add question
        </button>
      ) : (
        <p className="text-xs text-charcoal-600">Up to {max} questions.</p>
      )}
    </div>
  )
}
