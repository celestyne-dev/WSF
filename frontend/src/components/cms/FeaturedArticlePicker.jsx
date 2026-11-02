import { useState } from 'react'
import EntitySelect from './EntitySelect'
import { fetchArticles } from '../../api/articles'

// AI Search / GEO Phase 4C — the Topic/Series "Start here" picker: one
// cornerstone Article, chosen with the existing EntitySelect. Searches the
// public article list, so only PUBLISHED stories are offered (the backend
// still validates existence, and public pages independently hide a pick
// that is later unpublished). Value is the Article id.
async function searchPublishedArticles(query) {
  const res = await fetchArticles({ query, pageSize: 8 })
  return res.items.map((a) => ({ value: String(a.id), label: a.title, sublabel: a.authorName || undefined }))
}

export default function FeaturedArticlePicker({ value, selection, onChange }) {
  const [labels, setLabels] = useState({})
  async function loadOptions(query) {
    const options = await searchPublishedArticles(query)
    setLabels((prev) => ({ ...prev, ...Object.fromEntries(options.map((o) => [o.value, o.label])) }))
    return options
  }
  const current = value ? String(value) : null
  const resolveLabel = (v) => labels[v] || (selection && String(selection.id) === v ? selection.title : `Article #${v}`)
  const hidden = selection && current === String(selection.id) && selection.status !== 'published'
  return (
    <div className="space-y-2">
      <EntitySelect
        value={current}
        onChange={(v) => onChange(v ? Number(v) : null)}
        loadOptions={loadOptions}
        resolveLabel={resolveLabel}
        placeholder="Search published stories…"
      />
      {hidden && (
        <p className="text-xs text-amber-700">
          This story is currently {selection.status}, so the public page won&apos;t show it until it&apos;s published again.
        </p>
      )}
    </div>
  )
}
