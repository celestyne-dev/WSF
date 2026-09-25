import EntitySelect from './EntitySelect'
import { fetchTopics, fetchSeries } from '../../api/taxonomies'
import { fetchPagesAdmin } from '../../api/pages'
import { MENU_ITEM_STYLES } from '../../constants/navigationItems'

async function searchTopics(query) {
  const all = await fetchTopics()
  const q = (query || '').toLowerCase()
  return all.filter((t) => !q || t.name.toLowerCase().includes(q)).slice(0, 12).map((t) => ({ value: t.id, label: t.name }))
}

async function searchSeries(query) {
  const all = await fetchSeries()
  const q = (query || '').toLowerCase()
  return all.filter((s) => !q || s.name.toLowerCase().includes(q)).slice(0, 12).map((s) => ({ value: s.id, label: s.name }))
}

async function searchPages(query) {
  const res = await fetchPagesAdmin({ q: query, per_page: 10 })
  return res.items.map((p) => ({ value: p.id, label: p.title, sublabel: `/${p.slug}` }))
}

// EntitySelect's slug-based single-select works for numeric ids just as
// well (it never assumes a string) — this wraps it so callers here pass
// an id, get an id back, and see a real name instead of "42" once chosen.
function IdSelect({ value, onChange, loadOptions, placeholder }) {
  return (
    <EntitySelect
      value={value ? String(value) : null}
      onChange={(v) => onChange(v ? Number(v) : null)}
      loadOptions={async (q) => (await loadOptions(q)).map((o) => ({ ...o, value: String(o.value) }))}
      placeholder={placeholder}
    />
  )
}

function field(label, input) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</label>
      <div className="mt-1">{input}</div>
    </div>
  )
}

/** Renders only the fields relevant to `item.itemType` — see
 * MENU_ITEM_TYPE_LABELS for the controlled type list. No raw JSON, no
 * `if (type === ...)` chain living in the page component itself.
 */
export default function NavigationItemFields({ item, onChange }) {
  function patch(fields) {
    onChange({ ...item, ...fields })
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {field(
        'Label',
        <input
          value={item.label}
          onChange={(e) => patch({ label: e.target.value })}
          maxLength={100}
          placeholder="Menu label"
          className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
        />
      )}

      {item.itemType === 'route' &&
        field(
          'Internal path',
          <input
            value={item.url || ''}
            onChange={(e) => patch({ url: e.target.value })}
            placeholder="/opportunities"
            className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
          />
        )}

      {item.itemType === 'external' && (
        <>
          {field(
            'External URL',
            <input
              value={item.url || ''}
              onChange={(e) => patch({ url: e.target.value })}
              placeholder="https://example.com"
              className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          )}
          {field(
            '',
            <label className="mt-6 flex items-center gap-2 text-sm text-charcoal">
              <input type="checkbox" checked={!!item.openNewTab} onChange={(e) => patch({ openNewTab: e.target.checked })} />
              Open in new tab
            </label>
          )}
        </>
      )}

      {item.itemType === 'topic' &&
        field('Topic', <IdSelect value={item.topicId} onChange={(v) => patch({ topicId: v })} loadOptions={searchTopics} placeholder="Search topics…" />)}

      {item.itemType === 'series' &&
        field('Series', <IdSelect value={item.seriesId} onChange={(v) => patch({ seriesId: v })} loadOptions={searchSeries} placeholder="Search series…" />)}

      {item.itemType === 'page' &&
        field('Page', <IdSelect value={item.pageId} onChange={(v) => patch({ pageId: v })} loadOptions={searchPages} placeholder="Search pages…" />)}

      {item.itemType === 'group' && (
        <p className="self-end pb-2 text-xs text-charcoal-600">A grouping label with no link of its own — used to hold a dropdown.</p>
      )}

      {item.itemType !== 'group' &&
        field(
          'Presentation',
          <select
            value={item.style}
            onChange={(e) => patch({ style: e.target.value })}
            className="w-full border border-taupe-300 bg-white px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
          >
            {MENU_ITEM_STYLES.map((s) => (
              <option key={s} value={s}>
                {s === 'cta' ? 'CTA / button' : 'Standard link'}
              </option>
            ))}
          </select>
        )}
    </div>
  )
}
