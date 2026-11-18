import IdSelect from './IdSelect'
import { navEditorFields } from '../../utils/navigation'
import { searchPageIds as searchPages, searchSeriesIds as searchSeries, searchTopicIds as searchTopics } from '../../api/destinationSearch'
import { MENU_ITEM_STYLES } from '../../constants/navigationItems'

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
  // Picking a different Page/Topic/Series invalidates the server's preview.
  function pickEntity(field, id, label) {
    patch({ [field]: id, linkedLabel: label, effectiveUrl: null })
  }
  const shown = navEditorFields(item.itemType)

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
        shown.includes('url') &&
        field(
          'Internal path',
          <input
            value={item.url || ''}
            onChange={(e) => patch({ url: e.target.value })}
            required
            placeholder="/community"
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

      {shown.includes('topicId') &&
        field(
          'Topic',
          <IdSelect value={item.topicId} savedLabel={item.linkedLabel} onChange={(v, label) => pickEntity('topicId', v, label)} loadOptions={searchTopics} placeholder="Search topics…" />,
        )}

      {shown.includes('seriesId') &&
        field(
          'Series',
          <IdSelect value={item.seriesId} savedLabel={item.linkedLabel} onChange={(v, label) => pickEntity('seriesId', v, label)} loadOptions={searchSeries} placeholder="Search series…" />,
        )}

      {shown.includes('pageId') &&
        field(
          'Page',
          <IdSelect value={item.pageId} savedLabel={item.linkedLabel} onChange={(v, label) => pickEntity('pageId', v, label)} loadOptions={searchPages} placeholder="Search pages…" />,
        )}

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
