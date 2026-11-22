// Studio: structured editorial provenance for an Article. Each row is a
// recorded role (Reviewed by / Fact checked by / Expert contribution by)
// pointing at an existing Author or Person, never a typed name. Nothing is
// shown publicly unless a row exists here and that profile is public.
import { EXPERT_ROLES, todayInputValue } from '../../utils/articleProvenance'

const selectClass = 'w-full border border-taupe-300 bg-white px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

export default function ArticleProvenanceFields({ rows, onChange, authors, people, updatedAt, onUpdatedAtChange }) {
  function update(index, patch) {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }
  return (
    <div className="space-y-4">
      {rows.length === 0 && <p className="text-sm text-charcoal-600">No reviewer, fact-checker or expert is recorded. Nothing is shown publicly.</p>}
      {rows.map((row, index) => (
        <div key={index} className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[180px_1fr_auto]">
          <label className="block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Role
            <select value={row.role} onChange={(e) => update(index, { role: e.target.value })} className={`mt-1.5 ${selectClass}`}>
              {EXPERT_ROLES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Profile
            <select value={row.profile} onChange={(e) => update(index, { profile: e.target.value })} className={`mt-1.5 ${selectClass}`}>
              <option value="">Choose an Author or Person…</option>
              <optgroup label="Authors">
                {authors.map((a) => (
                  <option key={`a-${a.slug}`} value={`author:${a.slug}`}>{a.name}</option>
                ))}
              </optgroup>
              <optgroup label="People">
                {people.map((p) => (
                  <option key={`p-${p.slug}`} value={`person:${p.slug}`}>{p.name}</option>
                ))}
              </optgroup>
            </select>
          </label>
          <button type="button" onClick={() => onChange(rows.filter((_, i) => i !== index))} className="border border-taupe-300 px-3 py-2 text-sm text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600">
            Remove
          </button>
        </div>
      ))}
      {rows.length < 8 && (
        <button type="button" onClick={() => onChange([...rows, { role: 'reviewed_by', profile: '' }])} className="text-sm font-semibold text-burgundy-600 hover:underline">
          + Add reviewer or expert
        </button>
      )}
      <label className="block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
        Updated on <span className="normal-case text-charcoal-600/60">— only for a substantive update; shown as “Updated”</span>
        <input type="date" max={todayInputValue()} value={updatedAt} onChange={(e) => onUpdatedAtChange(e.target.value)} className={`mt-1.5 ${selectClass} sm:max-w-xs`} />
      </label>
    </div>
  )
}
