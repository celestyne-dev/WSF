import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { fetchPaymentConfig } from '../../api/payments'
import { validateAmountString } from '../../utils/money'

// WSF Checkout Phase 1 — the ONE admin pricing editor, shared by the Circle
// plan editor and the premium Resource editor. Each row is an explicit,
// admin-set price in one ISO 4217 currency (no live FX conversion):
//   { currency: 'USD', amount: '20.00', enabled: true }
// `amount` stays the typed decimal STRING (validated against the currency's
// own minor unit, never rounded); the backend converts it to integer minor
// units and is authoritative. Currencies come from the backend's single
// ISO 4217 registry (GET /payments/config) — never free text.
const inputClass = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

export default function MultiCurrencyPricingEditor({ prices = [], onChange }) {
  const [config, setConfig] = useState(null)

  useEffect(() => {
    let active = true
    fetchPaymentConfig()
      .then((data) => active && setConfig(data))
      .catch(() => active && setConfig({ defaultCurrency: 'USD', enabledCurrencies: [], currencies: [] }))
    return () => {
      active = false
    }
  }, [])

  const catalogue = useMemo(() => config?.currencies || [], [config])
  const byCode = useMemo(() => Object.fromEntries(catalogue.map((c) => [c.code, c])), [catalogue])
  const used = new Set(prices.map((p) => p.currency))

  function update(i, patch) {
    onChange(prices.map((row, idx) => (idx === i ? { ...row, ...patch } : row)))
  }

  function addPrice() {
    const preferred = [config?.defaultCurrency, ...(config?.enabledCurrencies || []), ...catalogue.map((c) => c.code)]
    const next = preferred.find((code) => code && !used.has(code))
    if (next) onChange([...prices, { currency: next, amount: '', enabled: true }])
  }

  if (!config) return <p className="text-xs text-charcoal-600/70">Loading currencies…</p>

  return (
    <div className="space-y-3">
      {prices.length === 0 && (
        <p className="border border-dashed border-taupe-300 px-4 py-5 text-center text-sm text-charcoal-600/70">
          No prices yet — add one to sell this online.
        </p>
      )}
      {prices.map((row, i) => {
        const info = byCode[row.currency]
        const error = row.amount === '' ? null : info ? validateAmountString(row.amount, info.minorUnit) : 'Choose a currency.'
        const notEnabledGlobally = config.enabledCurrencies.length > 0 && !config.enabledCurrencies.includes(row.currency)
        return (
          <div key={`${row.currency}-${i}`} className="border border-taupe-200 bg-white p-3">
            <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto_auto]">
              <label className="space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/80">Currency</span>
                <select value={row.currency} onChange={(e) => update(i, { currency: e.target.value })} className={inputClass}>
                  {catalogue.map((c) => (
                    <option key={c.code} value={c.code} disabled={c.code !== row.currency && used.has(c.code)}>
                      {c.code} — {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/80">
                  Amount{info ? ` (${info.minorUnit === 0 ? 'no decimals' : `up to ${info.minorUnit} decimals`})` : ''}
                </span>
                <input
                  inputMode="decimal"
                  value={row.amount}
                  onChange={(e) => update(i, { amount: e.target.value })}
                  placeholder={info?.minorUnit === 0 ? '2500' : '20.00'}
                  className={`${inputClass} ${error ? 'border-rose-500' : ''}`}
                />
              </label>
              <label className="flex items-center gap-2 pb-2 text-sm text-charcoal">
                <input type="checkbox" checked={!!row.enabled} onChange={(e) => update(i, { enabled: e.target.checked })} />
                Enabled
              </label>
              <button
                type="button"
                onClick={() => onChange(prices.filter((_, idx) => idx !== i))}
                aria-label={`Remove ${row.currency} price`}
                className="p-2 text-charcoal-600 hover:text-rose-600"
              >
                <Trash2 size={15} />
              </button>
            </div>
            {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
            {notEnabledGlobally && (
              <p className="mt-1 text-xs text-amber-700">
                {row.currency} isn&apos;t enabled in Settings → Payments, so it won&apos;t be offered at checkout yet.
              </p>
            )}
          </div>
        )
      })}
      <button
        type="button"
        onClick={addPrice}
        disabled={used.size >= catalogue.length}
        className="inline-flex items-center gap-1.5 border border-taupe-300 px-3 py-1.5 text-xs font-medium text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600 disabled:opacity-40"
      >
        <Plus size={13} /> Add price
      </button>
    </div>
  )
}

