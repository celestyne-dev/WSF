import { MAX_CAREER_GOALS, toggleGoal } from '../../utils/careerGoals'

// Career Hub goal chips (vocabulary from GET /career-hub/meta). Controlled:
// `value` is a list of goal keys; at most MAX_CAREER_GOALS can be chosen.
export default function CareerGoalsPicker({ goals, value, onChange, disabled = false }) {
  const selected = value || []
  return (
    <div>
      <div className="flex flex-wrap gap-2" role="group" aria-label={`Career goals (choose up to ${MAX_CAREER_GOALS})`}>
        {goals.map((g) => {
          const active = selected.includes(g.key)
          const blocked = !active && selected.length >= MAX_CAREER_GOALS
          return (
            <button
              key={g.key}
              type="button"
              aria-pressed={active}
              disabled={disabled || blocked}
              onClick={() => onChange(toggleGoal(selected, g.key))}
              className={`min-h-[40px] px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50 ${
                active ? 'bg-burgundy-600 text-ivory' : 'border border-taupe-300 bg-white text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600'
              }`}
            >
              {g.label}
            </button>
          )
        })}
      </div>
      <p className="mt-2 text-xs text-charcoal-600/70">
        Choose up to {MAX_CAREER_GOALS}. {selected.length}/{MAX_CAREER_GOALS} selected.
      </p>
    </div>
  )
}
