// `options` accepts plain strings ("Kenya") or { value, label } pairs
// (e.g. { value: 'KE', label: 'Kenya' }) so filters can key by a stable
// code (ISO country code, region name) while displaying a friendly label.
function normalize(opt) {
  return typeof opt === 'string' ? { value: opt, label: opt } : opt
}

export default function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-[10rem] border border-taupe-300 bg-white px-3 py-2 text-sm font-normal normal-case text-charcoal focus:border-burgundy-500 focus:outline-none"
      >
        <option value="">All</option>
        {options.map(normalize).map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  )
}
