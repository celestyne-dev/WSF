import { COUNTRIES } from '../../mock/geography'

const SORTED_COUNTRIES = [...COUNTRIES].sort((a, b) => a.name.localeCompare(b.name))

/**
 * Standardized country picker backed by the shared ISO country list —
 * used anywhere a person submits their own country (forms), rather than
 * a free-text field a backend would need to normalize later.
 */
export default function CountrySelect({ value, onChange, required, id, placeholder = 'Select your country' }) {
  return (
    <select
      id={id}
      required={required}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border border-taupe-300 bg-white px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
    >
      <option value="" disabled>
        {placeholder}
      </option>
      {SORTED_COUNTRIES.map((c) => (
        <option key={c.code} value={c.code}>
          {c.name}
        </option>
      ))}
    </select>
  )
}
