import { useEffect, useRef, useState } from 'react'
import { Search, X, GripVertical } from 'lucide-react'

/**
 * A searchable content selector for CMS relationships — Homepage Builder's
 * Article/Person/Series/Topic/Organization pickers all use this instead of
 * asking an editor to type a raw slug or ID. `loadOptions(query)` returns
 * `[{ value, label, sublabel? }]`; the caller is responsible for scoping
 * results to eligible (published) content — this component only presents
 * whatever it's given.
 *
 * Single mode: `value` is one slug string, `onChange(slug|null)`.
 * Multi mode (`multiple`): `value` is an ordered array of slugs,
 * `onChange(slugs)`. Selected chips can be reordered with up/down arrows
 * (no drag-and-drop dependency, per the "simplest robust interface"
 * guidance used for module ordering) and removed individually.
 */
export default function EntitySelect({ value, onChange, loadOptions, multiple = false, placeholder = 'Search…', resolveLabel }) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)
  // Remembers labels for slugs this instance has seen in a search result,
  // so an already-selected chip still shows a real title (not the bare
  // slug) after its search results scroll out of `options`. State (not a
  // ref) because it's read during render.
  const [labelCache, setLabelCache] = useState({})

  useEffect(() => {
    if (!open) return
    let active = true
    loadOptions(query)
      .then((results) => {
        if (!active) return
        setOptions(results)
        setLabelCache((prev) => ({ ...prev, ...Object.fromEntries(results.map((r) => [r.value, r.label])) }))
      })
      .catch(() => active && setOptions([]))
    return () => {
      active = false
    }
  }, [query, open, loadOptions])

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectedSlugs = multiple ? value || [] : value ? [value] : []

  function selectOption(option) {
    setLabelCache((prev) => ({ ...prev, [option.value]: option.label }))
    if (multiple) {
      if (!selectedSlugs.includes(option.value)) onChange([...selectedSlugs, option.value])
    } else {
      onChange(option.value)
    }
    setQuery('')
    setOpen(false)
  }

  function removeSlug(slug) {
    if (multiple) onChange(selectedSlugs.filter((s) => s !== slug))
    else onChange(null)
  }

  function move(index, direction) {
    const next = [...selectedSlugs]
    const target = index + direction
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return (
    <div ref={containerRef} className="relative">
      {selectedSlugs.length > 0 && (
        <ul className="mb-2 space-y-1.5">
          {selectedSlugs.map((slug, index) => (
            <li key={slug} className="flex items-center gap-2 border border-taupe-300 bg-white px-2.5 py-1.5 text-sm">
              {multiple && <GripVertical size={13} className="shrink-0 text-charcoal-600/40" />}
              <span className="flex-1 truncate text-charcoal">
                {resolveLabel ? resolveLabel(slug) : labelCache[slug] || slug}
              </span>
              {multiple && (
                <span className="flex shrink-0 flex-col">
                  <button type="button" onClick={() => move(index, -1)} disabled={index === 0} className="text-[10px] leading-none text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">▲</button>
                  <button type="button" onClick={() => move(index, 1)} disabled={index === selectedSlugs.length - 1} className="text-[10px] leading-none text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">▼</button>
                </span>
              )}
              <button type="button" onClick={() => removeSlug(slug)} aria-label={`Remove ${slug}`} className="shrink-0 text-charcoal-600 hover:text-rose-600">
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {(multiple || selectedSlugs.length === 0) && (
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-2.5 py-2">
          <Search size={14} className="text-charcoal-600" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setOpen(true)}
            placeholder={placeholder}
            className="w-full text-sm focus:outline-none"
          />
        </div>
      )}
      {open && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto border border-taupe-300 bg-white shadow-lg">
          {options.length === 0 && <li className="px-3 py-2 text-sm text-charcoal-600">No matches.</li>}
          {options.map((option) => (
            <li key={option.value}>
              <button
                type="button"
                onClick={() => selectOption(option)}
                disabled={selectedSlugs.includes(option.value)}
                className="flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-taupe-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <span className="text-charcoal">{option.label}</span>
                {option.sublabel && <span className="text-xs text-charcoal-600">{option.sublabel}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
