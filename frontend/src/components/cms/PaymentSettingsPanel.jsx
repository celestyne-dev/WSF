import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-toastify'
import { fetchAdminSettings, saveAdminSettings } from '../../api/admin'
import PageLoader from '../ui/PageLoader'

// WSF Checkout Phase 1 — Admin Settings -> Payments. Non-secret checkout
// configuration only: default/enabled currencies (from the backend's ISO
// 4217 registry — never free text) and per-provider method toggles. Provider
// credentials stay in server environment config; this panel only ever
// shows "Configured: Yes/No", never a key. The backend validates every
// field and stays authoritative (an admin toggle can narrow what a provider
// supports, never widen it).
export default function PaymentSettingsPanel() {
  const [data, setData] = useState(undefined)
  const [form, setForm] = useState(null)
  const [query, setQuery] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    fetchAdminSettings()
      .then((res) => {
        if (!active) return
        const payment = res?.payment_settings || null
        setData(payment)
        setForm(payment ? structuredClone(payment.settings) : null)
      })
      .catch(() => active && setData(null))
    return () => {
      active = false
    }
  }, [])

  const catalogue = useMemo(() => data?.currencies || [], [data])
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? catalogue.filter((c) => c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q)) : catalogue
  }, [catalogue, query])

  if (data === undefined) return <PageLoader />
  if (!data || !form) return <p className="text-sm text-charcoal-600">Payment settings couldn&apos;t be loaded.</p>

  function toggleCurrency(code) {
    setForm((prev) => {
      const enabled = prev.enabledCurrencies.includes(code)
        ? prev.enabledCurrencies.filter((c) => c !== code)
        : [...prev.enabledCurrencies, code]
      return { ...prev, enabledCurrencies: enabled }
    })
  }

  function setProvider(key, patch) {
    setForm((prev) => ({ ...prev, providers: { ...prev.providers, [key]: { ...prev.providers[key], ...patch } } }))
  }

  async function handleSave() {
    if (!form.enabledCurrencies.length) {
      toast.error('Enable at least one currency.')
      return
    }
    if (!form.enabledCurrencies.includes(form.defaultCurrency)) {
      toast.error('The default currency must be one of the enabled currencies.')
      return
    }
    setSaving(true)
    try {
      const res = await saveAdminSettings({ payment_settings: form })
      setData(res.payment_settings)
      setForm(structuredClone(res.payment_settings.settings))
      toast.success('Payment settings saved.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong saving payment settings.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Global</p>
        <div className="mt-3 max-w-sm">
          <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Default currency</label>
          <select
            value={form.defaultCurrency}
            onChange={(e) => setForm((prev) => ({ ...prev, defaultCurrency: e.target.value }))}
            className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm"
          >
            {form.enabledCurrencies.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-charcoal-600/70">Preselected at checkout when an item is priced in it.</p>
        </div>

        <div className="mt-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Enabled currencies</p>
          <p className="mt-0.5 text-xs text-charcoal-600/70">
            Selected: {form.enabledCurrencies.join(', ') || 'none'}. A currency is only charged when a provider also
            supports it.
          </p>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search currencies (e.g. USD, euro)…"
            className="mt-3 w-full max-w-sm border border-taupe-300 px-3 py-2 text-sm"
          />
          <div className="mt-3 grid max-h-72 grid-cols-1 gap-1 overflow-y-auto border border-taupe-200 p-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((c) => (
              <label key={c.code} className="flex items-center gap-2 text-sm text-charcoal">
                <input type="checkbox" checked={form.enabledCurrencies.includes(c.code)} onChange={() => toggleCurrency(c.code)} />
                <span className="font-semibold">{c.code}</span>
                <span className="truncate text-charcoal-600">{c.name}</span>
              </label>
            ))}
          </div>
        </div>
      </section>

      {Object.entries(data.providers).map(([key, provider]) => {
        const settings = form.providers[key]
        return (
          <section key={key} className="border-t border-taupe-200 pt-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{provider.label}</p>
            <p className="mt-1 text-sm text-charcoal">
              Configured on this server:{' '}
              <span className={provider.configured ? 'font-semibold text-emerald-700' : 'font-semibold text-rose-600'}>
                {provider.configured ? 'Yes' : 'No'}
              </span>
              <span className="ml-2 text-xs text-charcoal-600/70">Supports {provider.currencies.join(', ') || 'no currencies on this account'}</span>
            </p>
            {!provider.configured && (
              <p className="mt-1 text-xs text-amber-700">Provider credentials are not configured on this server.</p>
            )}
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal">
              <input type="checkbox" checked={!!settings.enabled} onChange={(e) => setProvider(key, { enabled: e.target.checked })} />
              Provider enabled
            </label>
            <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Methods</p>
            <div className="mt-2 space-y-2">
              {provider.methods.map((method) => (
                <label key={method.key} className="flex items-start gap-2 text-sm text-charcoal">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={!!settings.methods[method.key]}
                    onChange={(e) => setProvider(key, { methods: { ...settings.methods, [method.key]: e.target.checked } })}
                  />
                  <span>
                    <span className="font-medium">{method.label}</span>
                    <span className="block text-xs text-charcoal-600/70">
                      {method.description} Currencies: {method.currencies.join(', ') || '—'}.
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </section>
        )
      })}

      <button type="button" onClick={handleSave} disabled={saving} className="btn-primary disabled:opacity-60">
        {saving ? 'Saving…' : 'Save payment settings'}
      </button>
    </div>
  )
}
