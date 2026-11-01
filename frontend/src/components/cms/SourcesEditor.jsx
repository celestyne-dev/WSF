import { ChevronUp, ChevronDown, Trash2, Plus } from 'lucide-react'
import { MAX_SOURCES, blankSource } from '../../utils/sources'

// AI Search / GEO Phase 3A/4A — shared editor for Article.sources,
// Person.sources and Author.sources: the ordered reports/studies/official
// pages/news coverage a page relies on. Plain-text fields only (rendered
// as text everywhere, never HTML); the backend's schemas/sources.py
// SourceSchema is authoritative for validation (http(s) URLs only,
// title/url required, no duplicate URLs, at most 50). Array order is the
// public display order — Move up/down, no drag-and-drop dependency.

const inputClass = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'
const labelClass = 'text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/80'

export default function SourcesEditor({ sources = [], onChange }) {
  function update(i, field, value) {
    const next = [...sources]
    next[i] = { ...next[i], [field]: value }
    onChange(next)
  }
  function move(i, dir) {
    const target = i + dir
    if (target < 0 || target >= sources.length) return
    const next = [...sources]
    ;[next[i], next[target]] = [next[target], next[i]]
    onChange(next)
  }

  return (
    <div className="space-y-3">
      {sources.length === 0 && (
        <p className="border border-dashed border-taupe-300 px-4 py-6 text-center text-sm text-charcoal-600/70">No sources added yet.</p>
      )}
      {sources.map((source, i) => {
        const summary = [source.publisher, source.publishedDate].filter(Boolean).join(' · ')
        return (
          <div key={i} className="border border-taupe-200 bg-white p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-charcoal">
                  {i + 1}. {source.title || 'Untitled source'}
                </p>
                {source.url && <p className="truncate text-xs text-charcoal-600/70">{source.url}</p>}
                {summary && <p className="text-xs text-charcoal-600/70">{summary}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button type="button" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move source ${i + 1} up`} className="p-1.5 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
                  <ChevronUp size={15} />
                </button>
                <button type="button" onClick={() => move(i, 1)} disabled={i === sources.length - 1} aria-label={`Move source ${i + 1} down`} className="p-1.5 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
                  <ChevronDown size={15} />
                </button>
                <button type="button" onClick={() => onChange(sources.filter((_, idx) => idx !== i))} aria-label={`Remove source ${i + 1}`} className="p-1.5 text-charcoal-600 hover:text-rose-600">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="space-y-1 sm:col-span-2">
                <span className={labelClass}>Source title *</span>
                <input value={source.title} onChange={(e) => update(i, 'title', e.target.value)} maxLength={300} className={inputClass} />
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className={labelClass}>URL *</span>
                <input type="url" value={source.url} onChange={(e) => update(i, 'url', e.target.value)} placeholder="https://…" maxLength={2048} className={inputClass} />
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Publisher</span>
                <input value={source.publisher} onChange={(e) => update(i, 'publisher', e.target.value)} maxLength={250} className={inputClass} />
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Author</span>
                <input value={source.author} onChange={(e) => update(i, 'author', e.target.value)} maxLength={250} className={inputClass} />
              </label>
              <label className="space-y-1">
                <span className={labelClass}>Published date</span>
                <input type="date" value={source.publishedDate} onChange={(e) => update(i, 'publishedDate', e.target.value)} className={inputClass} />
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className={labelClass}>Note</span>
                <input value={source.note} onChange={(e) => update(i, 'note', e.target.value)} maxLength={500} placeholder="Optional short context" className={inputClass} />
              </label>
            </div>
          </div>
        )
      })}
      <button
        type="button"
        onClick={() => onChange([...sources, blankSource()])}
        disabled={sources.length >= MAX_SOURCES}
        className="inline-flex items-center gap-1.5 border border-taupe-300 px-3 py-1.5 text-xs font-medium text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600 disabled:opacity-40"
      >
        <Plus size={13} /> Add source
      </button>
    </div>
  )
}
