import { Plus, Trash2 } from 'lucide-react'
import { WORKPLACE_CLAIM_SOURCES, WORKPLACE_PRACTICES } from '../../constants/workplace'

const input = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

// Studio editor for an Organization's workplace practices. Each practice
// states where the claim comes from; "Publicly documented" and "Source
// reviewed by WSF" need a public source link (enforced by the API too).
export default function WorkplacePracticesEditor({ value, onChange }) {
  const rows = value || []
  const used = new Set(rows.map((r) => r.practice))
  const next = WORKPLACE_PRACTICES.find((p) => !used.has(p.value))

  function patch(i, fields) {
    onChange(rows.map((r, idx) => (idx === i ? { ...r, ...fields } : r)))
  }

  return (
    <div className="space-y-3">
      {rows.map((row, i) => (
        <div key={row.practice} className="space-y-2 border border-taupe-200 p-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <select value={row.practice} onChange={(e) => patch(i, { practice: e.target.value })} className={input} aria-label="Practice">
              {WORKPLACE_PRACTICES.filter((p) => p.value === row.practice || !used.has(p.value)).map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
            <select value={row.claimSource} onChange={(e) => patch(i, { claimSource: e.target.value })} className={input} aria-label="Claim source">
              {WORKPLACE_CLAIM_SOURCES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
            <button type="button" onClick={() => onChange(rows.filter((_, idx) => idx !== i))} aria-label="Remove practice" className="p-2 text-charcoal-600 hover:text-rose-600">
              <Trash2 size={15} />
            </button>
          </div>
          <input value={row.sourceUrl || ''} onChange={(e) => patch(i, { sourceUrl: e.target.value })} placeholder={row.claimSource === 'self_reported' ? 'Source link (optional)' : 'Source link (required), https://…'} className={input} />
          <input value={row.note || ''} onChange={(e) => patch(i, { note: e.target.value })} maxLength={280} placeholder="Short note (optional)" className={input} />
        </div>
      ))}
      {next && (
        <button type="button" onClick={() => onChange([...rows, { practice: next.value, claimSource: 'self_reported', sourceUrl: '', note: '' }])} className="inline-flex items-center gap-1 text-sm font-semibold text-burgundy-600 hover:underline">
          <Plus size={14} /> Add a practice
        </button>
      )}
    </div>
  )
}
