// WSF Checkout Phase 1 — shows an item's price and, only when it has more
// than one enabled price, lets the buyer choose the currency (preselected:
// the server's default, normally USD). No geolocation/IP guessing. The
// choice is just a currency code sent to checkout; the server loads that
// stored price and computes the amount itself. Payment-option copy lists
// only the methods the server reports as actually available for the
// selected currency (paymentMethods) — Paystack's hosted page then
// presents them; no card/M-PESA data ever touches WSF.
export default function CheckoutPriceSelector({ prices, selected, onSelect, suffix, size = 'lg', idPrefix = 'price' }) {
  const options = prices || []
  if (!options.length) return null
  const current = options.find((p) => p.currency === selected) || options[0]
  const methods = current.paymentMethods || []
  return (
    <div>
      <p className={size === 'lg' ? 'text-2xl font-semibold text-charcoal' : 'text-lg font-semibold text-charcoal'}>
        {current.formatted}
        {suffix && <span className="ml-1 text-sm font-normal text-charcoal-600/70">{suffix}</span>}
      </p>
      {options.length > 1 && (
        <label className="mt-2 flex items-center gap-2 text-xs text-charcoal-600" htmlFor={`${idPrefix}-currency`}>
          Pay in
          <select
            id={`${idPrefix}-currency`}
            value={current.currency}
            onChange={(e) => onSelect(e.target.value)}
            className="border border-taupe-300 px-2 py-1 text-xs"
          >
            {options.map((p) => (
              <option key={p.currency} value={p.currency}>
                {p.currency} — {p.formatted}
              </option>
            ))}
          </select>
        </label>
      )}
      {methods.length > 0 && (
        <p className="mt-2 text-xs text-charcoal-600/80">Payment options: {methods.map((m) => m.label).join(' · ')}</p>
      )}
    </div>
  )
}
