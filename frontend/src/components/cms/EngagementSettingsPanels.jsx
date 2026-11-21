import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { fetchAdminSettings, saveAdminSettings } from '../../api/admin'

// Studio -> Settings -> "Newsletter popup" and "Cookie consent". Plain text
// and bounded numbers only, validated again server-side (backend
// engagement_settings.py). There is deliberately no field for scripts,
// tracking IDs or HTML.

const input = 'rounded-control w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'
const label = 'text-xs font-semibold uppercase tracking-wide text-charcoal-600'

function useSettingsSection(key) {
  const [value, setValue] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    let active = true
    fetchAdminSettings()
      .then((data) => active && setValue(data[key] || {}))
      .catch(() => active && setError('Could not load these settings. Please try again.'))
    return () => {
      active = false
    }
  }, [key])
  async function save(next) {
    setSaving(true)
    try {
      const data = await saveAdminSettings({ [key]: next })
      setValue(data?.[key] || next)
      toast.success('Saved. Public pages use it from their next load.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || err?.apiError?.message || 'Could not save. Please check the values.')
    } finally {
      setSaving(false)
    }
  }
  return { value, setValue, error, saving, save }
}

function NumberField({ id, text, hint, value, onChange, min, max }) {
  return (
    <div>
      <label htmlFor={id} className={label}>{text}</label>
      <input id={id} type="number" min={min} max={max} value={value} onChange={(e) => onChange(Number.parseInt(e.target.value || '0', 10))} className={`${input} mt-1.5 sm:w-40`} />
      {hint && <p className="mt-1 text-xs text-charcoal-600">{hint}</p>}
    </div>
  )
}

function TextField({ id, text, value, onChange, max, multiline }) {
  const Tag = multiline ? 'textarea' : 'input'
  return (
    <div>
      <label htmlFor={id} className={label}>{text}</label>
      <Tag id={id} value={value || ''} maxLength={max} rows={multiline ? 3 : undefined} onChange={(e) => onChange(e.target.value)} className={`${input} mt-1.5`} />
      <p className="mt-1 text-xs text-charcoal-600">Plain text only, up to {max} characters.</p>
    </div>
  )
}

export function NewsletterPopupSettingsPanel() {
  const { value, setValue, error, saving, save } = useSettingsSection('newsletter_popup')
  if (error) return <p className="text-sm text-burgundy-600">{error}</p>
  if (!value) return <p className="text-sm text-charcoal-600">Loading…</p>
  const set = (k) => (v) => setValue({ ...value, [k]: v })
  return (
    <div className="max-w-2xl space-y-5">
      <p className="text-sm text-charcoal-600">
        The WSF Weekly popup uses the normal newsletter signup (same subscriber list, source “newsletter-popup”). It never opens
        on Studio, sign-in, account, newsletter, legal, checkout, certificate, form or lesson pages, and waits until a visitor has
        answered the cookie banner.
      </p>
      <label className="flex items-center gap-2 text-sm font-medium text-charcoal">
        <input type="checkbox" checked={value.enabled} onChange={(e) => set('enabled')(e.target.checked)} /> Show the popup
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <NumberField id="np-delay" text="Time on site (seconds)" hint="0 turns the time trigger off." value={value.delaySeconds} onChange={set('delaySeconds')} min={0} max={600} />
        <NumberField id="np-scroll" text="Scroll depth (%)" hint="Opens at whichever comes first. 0 turns this off." value={value.scrollPercent} onChange={set('scrollPercent')} min={0} max={100} />
        <NumberField id="np-dismiss" text="After closing, hide for (days)" value={value.dismissDays} onChange={set('dismissDays')} min={1} max={365} />
        <NumberField id="np-success" text="After signing up, hide for (days)" value={value.successDays} onChange={set('successDays')} min={1} max={3650} />
      </div>
      <TextField id="np-title" text="Title" value={value.title} onChange={set('title')} max={80} />
      <TextField id="np-body" text="Text" value={value.body} onChange={set('body')} max={240} multiline />
      <TextField id="np-cta" text="Button label" value={value.ctaLabel} onChange={set('ctaLabel')} max={40} />
      <p className="text-xs text-charcoal-600">
        The consent line under the form (“By subscribing, you agree to receive WSF emails…”) is fixed wording, recorded with each
        signup as version newsletter-v1. Avoid promising a send day or frequency here unless it is reliable.
      </p>
      <button type="button" onClick={() => save(value)} disabled={saving} className="btn-primary disabled:opacity-60">{saving ? 'Saving…' : 'Save popup settings'}</button>
    </div>
  )
}

export function CookieConsentSettingsPanel() {
  const { value, setValue, error, saving, save } = useSettingsSection('cookie_consent')
  if (error) return <p className="text-sm text-burgundy-600">{error}</p>
  if (!value) return <p className="text-sm text-charcoal-600">Loading…</p>
  const set = (k) => (v) => setValue({ ...value, [k]: v })
  return (
    <div className="max-w-2xl space-y-5">
      <p className="text-sm text-charcoal-600">
        Visitors choose Preferences, Analytics and Marketing separately; Essential technologies (sign-in, security, checkout, and
        storing this choice) are always on and cannot be switched off here. Optional technologies only run after consent.
      </p>
      <label className="flex items-center gap-2 text-sm font-medium text-charcoal">
        <input type="checkbox" checked={value.bannerEnabled} onChange={(e) => set('bannerEnabled')(e.target.checked)} /> Show the cookie banner to visitors who have not chosen yet
      </label>
      {!value.bannerEnabled && (
        <p className="rounded-control border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          With the banner off, visitors are not asked, so every optional category stays off unless they open “Cookie settings” in the footer.
        </p>
      )}
      <div>
        <label htmlFor="cc-version" className={label}>Consent version</label>
        <input id="cc-version" value={value.version} maxLength={20} onChange={(e) => set('version')(e.target.value)} className={`${input} mt-1.5 sm:w-48`} />
        <p className="mt-1 text-xs text-charcoal-600">Change this after a material change to the Cookie Policy or the categories: every visitor is asked again.</p>
      </div>
      <TextField id="cc-title" text="Banner title" value={value.title} onChange={set('title')} max={80} />
      <TextField id="cc-body" text="Banner text" value={value.body} onChange={set('body')} max={400} multiline />
      <button type="button" onClick={() => save(value)} disabled={saving} className="btn-primary disabled:opacity-60">{saving ? 'Saving…' : 'Save cookie consent'}</button>
    </div>
  )
}
