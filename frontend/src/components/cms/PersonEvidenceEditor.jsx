import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react'
import { isPublicHttpUrl } from '../../utils/personEvidence'

// Achievements / Awards / Career timeline with an optional source per
// claim (title + public https URL). A source can be typed or copied in one
// click from the profile's own Sources & References (copied, not linked by
// index, so reordering the reference list never re-targets a claim's
// evidence). Server re-validates: backend app/services/person_evidence.py.

const input = 'w-full border border-taupe-300 px-2.5 py-1.5 text-sm focus:border-burgundy-500 focus:outline-none'

const KINDS = {
  achievements: {
    blank: { text: '', date: '', sourceLabel: '', sourceUrl: '' },
    add: 'Add achievement',
    fields: [
      ['text', 'Achievement', 'First woman appointed to…', 'sm:col-span-3', 500],
      ['date', 'Date (optional)', '2025', '', 40],
    ],
  },
  awards: {
    blank: { name: '', issuer: '', date: '', sourceLabel: '', sourceUrl: '' },
    add: 'Add award',
    fields: [
      ['name', 'Award', 'Africa Fintech 40 Under 40', 'sm:col-span-2', 300],
      ['issuer', 'Issuing organization (optional)', 'Forbes Africa', 'sm:col-span-1', 200],
      ['date', 'Year (optional)', '2024', '', 40],
    ],
  },
  career_timeline: {
    blank: { year: '', title: '', organization: '', sourceLabel: '', sourceUrl: '' },
    add: 'Add milestone',
    fields: [
      ['year', 'Year / date', '2025', '', 40],
      ['title', 'Role or milestone', 'Chief Executive Officer', 'sm:col-span-2', 300],
      ['organization', 'Organization (optional)', 'Company name', 'sm:col-span-1', 200],
    ],
  },
}

export default function PersonEvidenceEditor({ kind, items, onChange, sources = [] }) {
  const config = KINDS[kind]
  const linkable = sources.filter((src) => src.url && src.title)
  const update = (i, patch) => onChange(items.map((item, idx) => (idx === i ? { ...item, ...patch } : item)))
  const move = (i, dir) => {
    const t = i + dir
    if (t < 0 || t >= items.length) return
    const copy = [...items]
    ;[copy[i], copy[t]] = [copy[t], copy[i]]
    onChange(copy)
  }

  return (
    <div className="space-y-3">
      {items.map((item, i) => {
        const badUrl = item.sourceUrl && !isPublicHttpUrl(item.sourceUrl)
        return (
          <fieldset key={i} className="border border-taupe-200 bg-white p-3">
            <legend className="sr-only">{`${config.add.replace('Add ', '')} ${i + 1}`}</legend>
            <div className="grid gap-2 sm:grid-cols-4">
              {config.fields.map(([field, label, placeholder, span, max]) => (
                <label key={field} className={`block ${span}`}>
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">{label}</span>
                  <input value={item[field] || ''} onChange={(e) => update(i, { [field]: e.target.value })} placeholder={placeholder} maxLength={max} className={`${input} mt-1`} />
                </label>
              ))}
            </div>
            <div className="mt-2 grid gap-2 border-t border-taupe-100 pt-2 sm:grid-cols-[1fr_1.4fr_auto]">
              <label className="block">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">Source label (optional)</span>
                <input value={item.sourceLabel || ''} onChange={(e) => update(i, { sourceLabel: e.target.value })} placeholder="Company announcement" maxLength={200} className={`${input} mt-1`} />
              </label>
              <label className="block">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">Source link (optional)</span>
                <input
                  value={item.sourceUrl || ''}
                  onChange={(e) => update(i, { sourceUrl: e.target.value.trim() })}
                  placeholder="https://…"
                  aria-invalid={badUrl || undefined}
                  className={`${input} mt-1 ${badUrl ? '!border-rose-500' : ''}`}
                />
              </label>
              <div className="flex items-end gap-1">
                <button type="button" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move item ${i + 1} up`} className="p-1.5 text-charcoal-600 disabled:opacity-30"><ChevronUp size={15} /></button>
                <button type="button" onClick={() => move(i, 1)} disabled={i === items.length - 1} aria-label={`Move item ${i + 1} down`} className="p-1.5 text-charcoal-600 disabled:opacity-30"><ChevronDown size={15} /></button>
                <button type="button" onClick={() => onChange(items.filter((_, idx) => idx !== i))} aria-label={`Remove item ${i + 1}`} className="p-1.5 text-charcoal-600 hover:text-rose-600"><Trash2 size={15} /></button>
              </div>
            </div>
            {badUrl && <p className="mt-1 text-xs text-rose-600" role="alert">Use a full public link starting with https://</p>}
            {linkable.length > 0 && (
              <label className="mt-2 flex flex-wrap items-center gap-2 text-xs text-charcoal-600">
                Use a reference:
                <select
                  value=""
                  onChange={(e) => {
                    const src = linkable[Number(e.target.value)]
                    if (src) update(i, { sourceLabel: src.title, sourceUrl: src.url })
                  }}
                  className="max-w-full border border-taupe-300 bg-white px-2 py-1 text-xs"
                >
                  <option value="">Choose from Sources &amp; references…</option>
                  {linkable.map((src, idx) => (
                    <option key={src.url} value={idx}>{src.title}</option>
                  ))}
                </select>
              </label>
            )}
          </fieldset>
        )
      })}
      <button type="button" onClick={() => onChange([...items, { ...config.blank }])} className="inline-flex items-center gap-1 text-xs font-semibold text-burgundy-600">
        <Plus size={13} aria-hidden="true" /> {config.add}
      </button>
    </div>
  )
}
