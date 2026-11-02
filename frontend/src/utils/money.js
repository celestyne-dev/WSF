// WSF Checkout Phase 1 — pure, float-free money helpers for the admin
// pricing editor and checkout UI. Amounts the admin types stay STRINGS and
// are validated against the currency's ISO 4217 minor unit (from the
// backend catalogue); the backend converts them to integer minor units
// (app/services/money.py) and is authoritative. Display strings come from
// the server (`formatted`) — nothing here ever does floating-point money.

// "19.99" with minorUnit 2 -> null (ok) | error message. Never rounds.
export function validateAmountString(value, minorUnit) {
  const text = String(value ?? '').trim()
  if (!text) return 'Enter an amount.'
  if (!/^\d+(\.\d+)?$/.test(text)) return 'Enter a positive number like 19.99 (digits and one decimal point only).'
  const decimals = text.includes('.') ? text.split('.')[1].length : 0
  if (decimals > minorUnit) {
    return minorUnit === 0 ? 'This currency has no decimal places.' : `This currency allows at most ${minorUnit} decimal places.`
  }
  if (/^0*(\.0*)?$/.test(text)) return 'The amount must be greater than zero.'
  return null
}

// Integer minor units -> exact major-unit string using string math only:
// (1999, 2) -> "19.99", (250000, 2) -> "2500.00", (2500, 0) -> "2500".
export function minorToAmountString(amountMinor, minorUnit) {
  if (!Number.isInteger(amountMinor) || amountMinor < 0) return ''
  const digits = String(amountMinor).padStart(minorUnit + 1, '0')
  if (minorUnit === 0) return digits
  return `${digits.slice(0, -minorUnit)}.${digits.slice(-minorUnit)}`
}

// Admin pricing rows -> API payload. Rows keep `amount` as the typed
// string; the server does the minor-unit conversion.
export function pricesToPayload(rows) {
  return (rows || []).map((r) => ({ currency: r.currency, amount: String(r.amount ?? '').trim(), enabled: !!r.enabled }))
}

// Admin dump rows -> editor rows (keeps the server's exact decimal string).
export function pricesToRows(prices) {
  return (prices || []).map((p) => ({ currency: p.currency, amount: p.amount ?? '', enabled: p.enabled ?? true }))
}

// Client-side checks for the pricing editor (backend re-validates). With a
// catalogue, amounts are checked against each currency's minor unit;
// without one, only structural checks run (minor-unit rules stay server-side).
export function validatePriceRows(rows, catalogue, { requireEnabled = false } = {}) {
  const byCode = catalogue ? Object.fromEntries(catalogue.map((c) => [c.code, c])) : null
  const seen = new Set()
  for (const [i, row] of (rows || []).entries()) {
    const label = `Price ${i + 1}`
    const info = byCode ? byCode[row.currency] : { minorUnit: 4 }
    if (!info || !/^[A-Z]{3}$/.test(row.currency || '')) return `${label}: choose a currency.`
    if (seen.has(row.currency)) return `${row.currency} is listed more than once — one price per currency.`
    seen.add(row.currency)
    const error = validateAmountString(row.amount, info.minorUnit)
    if (error) return `${label} (${row.currency}): ${error}`
  }
  if (requireEnabled && !(rows || []).some((r) => r.enabled)) return 'Enable at least one price.'
  return null
}

// The price option to preselect — the same order as the backend's
// pricing.preferred_currency(): (1) the default currency if it can be
// checked out, (2) the first checkout-available option, (3) the default
// currency even if unavailable (display only), (4) the first option, (5) null.
export function pickDefaultPrice(prices, defaultCurrency) {
  const list = prices || []
  return (
    list.find((p) => p.currency === defaultCurrency && p.checkoutAvailable) ||
    list.find((p) => p.checkoutAvailable) ||
    list.find((p) => p.currency === defaultCurrency) ||
    list[0] ||
    null
  )
}

export const UNAVAILABLE_CURRENCY_MESSAGE = "Online payment isn't available in this currency right now."

// Currency <select> options: every price stays visible, but one that can't
// be checked out right now is disabled (never selectable as if payable).
export function priceSelectorOptions(prices) {
  return (prices || []).map((p) => ({
    value: p.currency,
    label: p.checkoutAvailable ? `${p.currency} — ${p.formatted}` : `${p.currency} — ${p.formatted} — unavailable online`,
    disabled: !p.checkoutAvailable,
  }))
}

// The option a buyer has effectively selected (their choice, else the
// payable default) and whether a checkout POST may be sent for it. Items
// with no price options (legacy/mock data) keep the old behavior: the
// backend decides. The backend stays authoritative either way.
export function selectedPriceOption(prices, selectedCurrency, defaultCurrency) {
  const list = prices || []
  return list.find((p) => p.currency === selectedCurrency) || pickDefaultPrice(list, defaultCurrency)
}

export function canCheckoutPrice(prices, selectedCurrency, defaultCurrency) {
  if (!prices || prices.length === 0) return true
  return !!selectedPriceOption(prices, selectedCurrency, defaultCurrency)?.checkoutAvailable
}
