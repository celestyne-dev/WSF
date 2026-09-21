import { useSelector } from 'react-redux'

/**
 * Standardized country picker backed by the shared Country reference table
 * (GET /api/v1/public/countries in real mode, the static list in mock
 * mode) — loaded once into Redux by PublicLayout via api/geography.js's
 * fetchCountries(). This component only ever reads Redux state; it has no
 * import of its own into the mock data directory, so real mode is never
 * one render away from showing dev-only fixture countries.
 */
export default function CountrySelect({ value, onChange, required, id, placeholder = 'Select your country' }) {
  const countries = useSelector((s) => s.site.countries)
  const sorted = [...countries].sort((a, b) => a.name.localeCompare(b.name))

  return (
    <select
      id={id}
      required={required}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={!countries.length}
      className="w-full border border-taupe-300 bg-white px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none disabled:opacity-60"
    >
      <option value="" disabled>
        {countries.length ? placeholder : 'Loading countries…'}
      </option>
      {sorted.map((c) => (
        <option key={c.code} value={c.code}>
          {c.name}
        </option>
      ))}
    </select>
  )
}
