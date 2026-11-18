import { ESTIMATED_TIME_UNIT_OPTIONS } from '../../constants/careerMetadata'

const inputClass = 'w-24 border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

/**
 * Optional "estimated time" for a Resource: how long a reader should
 * expect to spend using or completing it (NOT a video/audio duration).
 * Leave the unit empty for no estimate; "Self-paced" takes no number; an
 * upper bound turns it into a range (30–45 min).
 */
export default function EstimatedTimeFields({ form, updateField }) {
  const unit = form.estimatedTimeUnit || ''
  const numeric = unit && unit !== 'self_paced'
  return (
    <fieldset className="border-0 p-0">
      <legend className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Estimated time (optional)</legend>
      <p className="mt-1 text-xs text-charcoal-600/80">
        How long a reader should expect to spend using or completing this — e.g. 10 min, 30–45 min, 2 hours, 7 days, 4 weeks, or self-paced. Not a video length.
      </p>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-charcoal-600">
          Unit
          <select
            value={unit}
            onChange={(e) => {
              const next = e.target.value
              updateField('estimatedTimeUnit', next)
              if (!next || next === 'self_paced') {
                updateField('estimatedTimeValue', '')
                updateField('estimatedTimeMaxValue', '')
              }
            }}
            className="border border-taupe-300 px-3 py-2 text-sm"
          >
            <option value="">No estimate</option>
            {ESTIMATED_TIME_UNIT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        {numeric && (
          <>
            <label className="flex flex-col gap-1 text-xs text-charcoal-600">
              From
              <input type="number" min="1" value={form.estimatedTimeValue} onChange={(e) => updateField('estimatedTimeValue', e.target.value)} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1 text-xs text-charcoal-600">
              To (optional, for a range)
              <input type="number" min="1" value={form.estimatedTimeMaxValue} onChange={(e) => updateField('estimatedTimeMaxValue', e.target.value)} className={inputClass} />
            </label>
          </>
        )}
      </div>
    </fieldset>
  )
}
