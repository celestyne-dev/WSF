import { ChevronUp, ChevronDown, Trash2, Plus } from 'lucide-react'
import { MAX_CREDENTIALS, blankCredential } from '../../utils/credentials'

// AI Search / GEO Phase 4B — shared editor for Person.credentials and
// Author.credentials (same UX as SourcesEditor). Plain-text fields only;
// the backend's schemas/credentials.py is authoritative (name required,
// optional public http(s) link, no repeated name+issuer, at most 30).
// Array order is the public display order. An entry records what the
// profile states — never presented as verified.

const inputClass = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'
const labelClass = 'text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/80'

export default function CredentialsEditor({ credentials = [], onChange }) {
  function update(i, field, value) {
    const next = [...credentials]
    next[i] = { ...next[i], [field]: value }
    onChange(next)
  }
  function move(i, dir) {
    const target = i + dir
    if (target < 0 || target >= credentials.length) return
    const next = [...credentials]
    ;[next[i], next[target]] = [next[target], next[i]]
    onChange(next)
  }

  return (
    <div className="space-y-3">
      {credentials.length === 0 && (
        <p className="border border-dashed border-taupe-300 px-4 py-6 text-center text-sm text-charcoal-600/70">No credentials added yet.</p>
      )}
      {credentials.map((credential, i) => {
        const summary = [credential.category, credential.issuer].filter(Boolean).join(' · ')
        return (
          <div key={i} className="border border-taupe-200 bg-white p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-charcoal">
                  {i + 1}. {credential.name || 'Untitled credential'}
                </p>
                {summary && <p className="truncate text-xs text-charcoal-600/70">{summary}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button type="button" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move credential ${i + 1} up`} className="p-1.5 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
                  <ChevronUp size={15} />
                </button>
                <button type="button" onClick={() => move(i, 1)} disabled={i === credentials.length - 1} aria-label={`Move credential ${i + 1} down`} className="p-1.5 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
                  <ChevronDown size={15} />
                </button>
                <button type="button" onClick={() => onChange(credentials.filter((_, idx) => idx !== i))} aria-label={`Remove credential ${i + 1}`} className="p-1.5 text-charcoal-600 hover:text-rose-600">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="space-y-1 sm:col-span-2">
                <span className={labelClass}>Name *</span>
                <input value={credential.name} onChange={(e) => update(i, 'name', e.target.value)} maxLength={250} placeholder="e.g. MBA, Chartered Accountant, Certified Digital Marketing Professional" className={inputClass} />
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Category</span>
                <input value={credential.category} onChange={(e) => update(i, 'category', e.target.value)} maxLength={100} placeholder="e.g. Degree, Certification, Licence" className={inputClass} />
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Issuer</span>
                <input value={credential.issuer} onChange={(e) => update(i, 'issuer', e.target.value)} maxLength={250} className={inputClass} />
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className={labelClass}>Public URL</span>
                <input type="url" value={credential.url} onChange={(e) => update(i, 'url', e.target.value)} placeholder="https://…" maxLength={2048} className={inputClass} />
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className={labelClass}>Note</span>
                <input value={credential.note} onChange={(e) => update(i, 'note', e.target.value)} maxLength={500} placeholder="Optional short context" className={inputClass} />
              </label>
            </div>
          </div>
        )
      })}
      <button
        type="button"
        onClick={() => onChange([...credentials, blankCredential()])}
        disabled={credentials.length >= MAX_CREDENTIALS}
        className="inline-flex items-center gap-1.5 border border-taupe-300 px-3 py-1.5 text-xs font-medium text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600 disabled:opacity-40"
      >
        <Plus size={13} /> Add credential
      </button>
    </div>
  )
}
