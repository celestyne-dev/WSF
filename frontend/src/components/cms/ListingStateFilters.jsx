import { EFFECTIVE_STATE_LABELS } from '../../utils/listingDates'

// Studio quick filters for Jobs/Opportunities. Values are sent as `state`
// and resolved server-side from status + dates (no extra stored statuses).
export function ListingStateFilters({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {[['', 'All'], ...options].map(([key, text]) => (
        <button
          key={key || 'all'}
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(key)}
          className={`rounded-control border px-3 py-1.5 text-xs font-semibold ${value === key ? 'border-charcoal bg-charcoal text-ivory' : 'border-taupe-300 bg-white text-charcoal-600 hover:text-charcoal'}`}
        >
          {text}
        </button>
      ))}
    </div>
  )
}

const TONES = {
  open: 'bg-emerald-50 text-emerald-800',
  closing_soon: 'bg-amber-50 text-amber-900',
  deadline_passed: 'bg-rose-50 text-rose-800',
  upcoming: 'bg-sky-50 text-sky-900',
}

// "Published · Deadline passed" style label; the words carry the meaning,
// the tint is only a secondary cue.
export function EffectiveStateBadge({ state }) {
  if (!state) return <span className="text-charcoal-600">—</span>
  return (
    <span className={`inline-block rounded-control px-2 py-0.5 text-[11px] font-semibold ${TONES[state] || 'bg-taupe-100 text-charcoal-600'}`}>
      {EFFECTIVE_STATE_LABELS[state] || state}
    </span>
  )
}
