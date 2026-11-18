import { useState } from 'react'
import EntitySelect from './EntitySelect'

// EntitySelect's slug-based single-select works for numeric ids just as
// well (it never assumes a string) — this wraps it so callers pass an id,
// get (id, label) back, and see the real name rather than a bare id: from
// this session's search results, or `savedLabel` (the server's
// linkedLabel) for an item loaded already linked.
export default function IdSelect({ value, savedLabel, onChange, loadOptions, placeholder }) {
  const [labels, setLabels] = useState({})
  return (
    <EntitySelect
      value={value ? String(value) : null}
      onChange={(v) => onChange(v ? Number(v) : null, v ? labels[v] || null : null)}
      loadOptions={async (q) => {
        const options = (await loadOptions(q)).map((o) => ({ ...o, value: String(o.value) }))
        setLabels((prev) => ({ ...prev, ...Object.fromEntries(options.map((o) => [o.value, o.label])) }))
        return options
      }}
      resolveLabel={(v) => labels[v] || savedLabel || `#${v}`}
      placeholder={placeholder}
    />
  )
}
