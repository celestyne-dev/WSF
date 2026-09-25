import { useState } from 'react'
import { ChevronUp, ChevronDown, Trash2, Plus, Eye, EyeOff, AlertTriangle } from 'lucide-react'
import NavigationItemFields from './NavigationItemFields'
import { MENU_ITEM_TYPE_LABELS, MENU_MAX_DEPTH, newNavItem } from '../../constants/navigationItems'

/** One row in the navigation tree editor, recursive over `item.children`.
 * `depth` is 1 for a top-level item — MENU_MAX_DEPTH caps how deep "Add
 * child" will go, matching the backend's own depth validation.
 */
export default function NavigationItemRow({ item, depth, siblingCount, index, onChange, onRemove, onMove }) {
  const [expanded, setExpanded] = useState(false)

  function patchChildren(nextChildren) {
    onChange({ ...item, children: nextChildren })
  }

  function updateChild(childIndex, nextChild) {
    const next = [...item.children]
    next[childIndex] = nextChild
    patchChildren(next)
  }

  function removeChild(childIndex) {
    patchChildren(item.children.filter((_, i) => i !== childIndex))
  }

  function moveChild(childIndex, direction) {
    const next = [...item.children]
    const target = childIndex + direction
    if (target < 0 || target >= next.length) return
    ;[next[childIndex], next[target]] = [next[target], next[childIndex]]
    patchChildren(next)
  }

  function addChild() {
    patchChildren([...item.children, newNavItem('route')])
    setExpanded(true)
  }

  return (
    <div className="border border-taupe-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 p-3">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <button type="button" onClick={() => onMove(index, -1)} disabled={index === 0} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">
              <ChevronUp size={14} />
            </button>
            <button type="button" onClick={() => onMove(index, 1)} disabled={index === siblingCount - 1} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">
              <ChevronDown size={14} />
            </button>
          </div>
          <button type="button" onClick={() => setExpanded((e) => !e)} className="text-left">
            <p className="text-sm font-semibold text-charcoal">{item.label || <span className="italic text-charcoal-600/60">Untitled</span>}</p>
            <p className="text-xs text-charcoal-600">
              {MENU_ITEM_TYPE_LABELS[item.itemType]}
              {item.effectiveUrl ? ` · ${item.effectiveUrl}` : ''}
            </p>
          </button>
          {item.warnings?.length > 0 && (
            <span title={item.warnings.join(' ')} className="flex items-center gap-1 text-amber-700">
              <AlertTriangle size={14} />
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onChange({ ...item, visible: !item.visible })}
            className="flex items-center gap-1.5 border border-taupe-300 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600 hover:border-burgundy-500"
          >
            {item.visible ? <Eye size={12} /> : <EyeOff size={12} />}
            {item.visible ? 'Visible' : 'Hidden'}
          </button>
          <select
            value={item.itemType}
            onChange={(e) => onChange({ ...item, itemType: e.target.value, url: e.target.value === 'route' ? item.url || '/' : null })}
            className="border border-taupe-300 bg-white px-2 py-1 text-xs focus:border-burgundy-500 focus:outline-none"
          >
            {Object.entries(MENU_ITEM_TYPE_LABELS).map(([type, label]) => (
              <option key={type} value={type}>
                {label}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => onRemove(index)} aria-label="Remove item" className="text-charcoal-600 hover:text-rose-600">
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-taupe-200 p-3">
          {item.warnings?.length > 0 && (
            <div className="mb-3 flex items-start gap-2 border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" />
              <ul>
                {item.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          <NavigationItemFields item={item} onChange={onChange} />

          {depth < MENU_MAX_DEPTH && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Dropdown children</p>
              <div className="mt-2 space-y-2 pl-4">
                {item.children.map((child, childIndex) => (
                  <NavigationItemRow
                    key={child.id}
                    item={child}
                    depth={depth + 1}
                    siblingCount={item.children.length}
                    index={childIndex}
                    onChange={(next) => updateChild(childIndex, next)}
                    onRemove={removeChild}
                    onMove={moveChild}
                  />
                ))}
                <button type="button" onClick={addChild} className="btn-secondary !px-3 !py-1.5 text-xs">
                  <Plus size={13} /> Add child
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
