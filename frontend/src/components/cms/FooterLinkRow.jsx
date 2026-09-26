import { ChevronUp, ChevronDown, Trash2, AlertTriangle } from 'lucide-react'
import NavigationItemFields from './NavigationItemFields'
import { FOOTER_LINK_TYPES, FOOTER_LINK_TYPE_LABELS, LEGAL_LINK_PATHS } from '../../constants/footerItems'

/** One footer link — flat, never recursive (a footer group is Group ->
 * Links, no dropdown-of-dropdowns; see spec's "no multi-level nested
 * tree" requirement). Reuses NavigationItemFields for the actual
 * type-specific inputs (route/page/topic/series/external + entity
 * search selectors) rather than a second, footer-only field set.
 */
export default function FooterLinkRow({ item, index, siblingCount, onChange, onRemove, onMove }) {
  const isLegalLink = item.effectiveUrl && LEGAL_LINK_PATHS.includes(item.effectiveUrl)

  function handleRemove() {
    const message = isLegalLink
      ? `"${item.label || 'This link'}" points to a legal page (${item.effectiveUrl}). Removing it from this group may leave a required legal link missing from the footer. Remove anyway?`
      : `Remove "${item.label || 'this link'}"? This never deletes the Page/Topic/Series/content it links to.`
    if (window.confirm(message)) onRemove()
  }

  return (
    <div className="border border-taupe-200 bg-white p-3">
      <div className="flex items-center gap-2">
        <div className="flex flex-col">
          <button type="button" disabled={index === 0} onClick={() => onMove(-1)} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-30">
            <ChevronUp size={14} />
          </button>
          <button type="button" disabled={index === siblingCount - 1} onClick={() => onMove(1)} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-30">
            <ChevronDown size={14} />
          </button>
        </div>

        <select
          value={item.itemType}
          onChange={(e) => onChange({ ...item, itemType: e.target.value, url: e.target.value === 'route' || e.target.value === 'external' ? item.url : null })}
          className="border border-taupe-300 bg-white px-2 py-1.5 text-xs focus:border-burgundy-500 focus:outline-none"
        >
          {FOOTER_LINK_TYPES.map((t) => (
            <option key={t} value={t}>
              {FOOTER_LINK_TYPE_LABELS[t]}
            </option>
          ))}
        </select>

        <div className="flex-1" />

        {item.warnings?.length > 0 && (
          <span title={item.warnings.join(' ')} className="text-amber-600">
            <AlertTriangle size={16} />
          </span>
        )}

        <button
          type="button"
          onClick={() => onChange({ ...item, visible: !item.visible })}
          className={`px-2 py-1 text-xs font-semibold uppercase tracking-wide ${item.visible ? 'text-charcoal-600' : 'bg-taupe-200 text-charcoal-600'}`}
        >
          {item.visible ? 'Visible' : 'Hidden'}
        </button>

        <button type="button" onClick={handleRemove} className="text-charcoal-600 hover:text-burgundy-600" aria-label="Remove link">
          <Trash2 size={16} />
        </button>
      </div>

      {item.warnings?.length > 0 && (
        <p className="mt-2 text-xs text-amber-700">{item.warnings.join(' ')}</p>
      )}

      <div className="mt-3">
        <NavigationItemFields item={item} onChange={onChange} />
      </div>
    </div>
  )
}
