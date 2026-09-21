import { useSelector } from 'react-redux'
import { COUNTRIES } from '../../mock/geography'

/**
 * Standardized country picker backed by the shared Country reference table
 * (GET /api/v1/public/countries, loaded once into Redux by PublicLayout) —
 * used anywhere a person submits their own country (forms), rather than a
 * free-text field a backend would need to normalize later. Falls back to
 * the static list before the real countries have loaded, or in mock mode.
 */
export default function CountrySelect({ value, onChange, required, id, placeholder = 'Select your country' }) {
  const loaded = useSelector((s) => s.site.countries)
  const countries = loaded.length ? loaded : COUNTRIES
  const sorted = [...countries].sort((a, b) => a.name.localeCompare(b.name))

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
      {sorted.map((c) => (
        <option key={c.code} value={c.code}>
          {c.name}
        </option>
      ))}
    </select>
  )
}
