import useSettingsSection from '../../hooks/useSettingsSection'

// Studio -> Settings -> "Newsletter popup" and "Cookie consent". Plain text
// and bounded numbers only, validated again server-side (backend
// engagement_settings.py). There is deliberately no field for scripts,
// tracking IDs or HTML.

const input = 'rounded-control w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'
const label = 'text-xs font-semibold uppercase tracking-wide text-charcoal-600'

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

// Studio -> Settings -> Newsletter: what /newsletter tells readers about WSF
// Weekly. "Sending schedule" stays empty unless a real, reliable schedule
// exists, so the page never promises a frequency nobody configured.
export function NewsletterPageSettingsPanel() {
  const { value, setValue, error, saving, save } = useSettingsSection('newsletter_page')
  if (error) return <p className="text-sm text-burgundy-600">{error}</p>
  if (!value) return <p className="text-sm text-charcoal-600">Loading…</p>
  const set = (k) => (v) => setValue({ ...value, [k]: v })
  const benefits = Array.isArray(value.benefits) ? value.benefits : []
  return (
    <div className="max-w-2xl space-y-5">
      <h2 className="font-serif text-xl font-semibold text-charcoal">WSF Weekly page</h2>
      <TextField id="nl-title" text="Title" value={value.title} onChange={set('title')} max={60} />
      <TextField id="nl-tagline" text="Tagline" value={value.tagline} onChange={set('tagline')} max={160} />
      <TextField id="nl-intro" text="Introduction (optional)" value={value.intro} onChange={set('intro')} max={400} multiline />
      <TextField id="nl-cadence" text="Sending schedule (optional)" value={value.cadence} onChange={set('cadence')} max={80} />
      <div>
        <label htmlFor="nl-benefits" className={label}>What readers get (one per line, up to 8)</label>
        <textarea
          id="nl-benefits"
          rows={6}
          value={benefits.join('\n')}
          onChange={(e) => set('benefits')(e.target.value.split('\n').slice(0, 8))}
          className={`${input} mt-1.5`}
        />
      </div>
      <button
        type="button"
        onClick={() => save({ ...value, benefits: benefits.map((b) => b.trim()).filter(Boolean) })}
        disabled={saving}
        className="btn-primary disabled:opacity-60"
      >
        {saving ? 'Saving…' : 'Save WSF Weekly page'}
      </button>
    </div>
  )
}

// Studio -> Settings -> "Comments" (backend app/services/comment_settings.py).
// Bounded numbers, switches and a blocked-words list only; no secrets.
export function CommentSettingsPanel() {
  const { value, setValue, error, saving, save } = useSettingsSection('comments')
  if (error) return <p className="text-sm text-burgundy-600">{error}</p>
  if (!value) return <p className="text-sm text-charcoal-600">Loading…</p>
  const set = (k) => (v) => setValue({ ...value, [k]: v })
  const words = (value.blockedWords || []).join('\n')
  return (
    <div className="max-w-2xl space-y-5">
      <p className="text-sm text-charcoal-600">
        Signed-in members can comment on articles. A member’s first comments wait for a moderator; comments with more than two
        links or a blocked word always wait, even from trusted members. Each article can also turn comments off or close them
        after a number of days (Article editor).
      </p>
      <label className="flex items-center gap-2 text-sm font-medium text-charcoal">
        <input type="checkbox" checked={value.enabled} onChange={(e) => set('enabled')(e.target.checked)} /> Allow new comments on articles
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <NumberField id="cm-trust" text="Approved comments for trusted status" hint="Until a member has this many published comments, each new one waits for approval." value={value.trustedThreshold} onChange={set('trustedThreshold')} min={1} max={50} />
        <NumberField id="cm-reports" text="Reports that hide a comment" hint="Unique members reporting the same comment. It is hidden for review, never deleted." value={value.reportHideThreshold} onChange={set('reportHideThreshold')} min={1} max={50} />
        <NumberField id="cm-min" text="Minimum time to write (seconds)" hint="Faster submissions are refused as automated." value={value.minSubmitSeconds} onChange={set('minSubmitSeconds')} min={1} max={60} />
      </div>
      <div>
        <label htmlFor="cm-words" className={label}>Blocked words and phrases</label>
        <textarea id="cm-words" rows={6} value={words} className={`${input} mt-1.5 font-mono`}
          onChange={(e) => set('blockedWords')(e.target.value.split('\n'))} aria-describedby="cm-words-hint" />
        <p id="cm-words-hint" className="mt-1 text-xs text-charcoal-600">
          One per line. Matches whole words, ignoring case (“scam” does not match “scammer”; write “scam*” to match words starting with it).
          A match holds the comment for review; nothing is deleted.
        </p>
      </div>
      <label className="flex items-center gap-2 text-sm font-medium text-charcoal">
        <input type="checkbox" checked={value.replyNotificationsEnabled} onChange={(e) => set('replyNotificationsEnabled')(e.target.checked)} />
        Let members opt in to an email when someone replies to their comment (off for each member until they choose it)
      </label>
      <button type="button" disabled={saving} className="btn-primary disabled:opacity-60"
        onClick={() => save({ ...value, blockedWords: (value.blockedWords || []).map((w) => w.trim()).filter(Boolean) })}>
        {saving ? 'Saving…' : 'Save comment settings'}
      </button>
    </div>
  )
}

// Studio -> Settings -> "Retention" (backend app/services/retention.py).
// Bounded whole numbers only; the server rejects anything outside the range.
export function RetentionSettingsPanel() {
  const { value, setValue, error, saving, save } = useSettingsSection('retention')
  if (error) return <p className="text-sm text-burgundy-600">{error}</p>
  if (!value || !value.values) return <p className="text-sm text-charcoal-600">Loading…</p>
  const set = (k) => (v) => setValue({ ...value, values: { ...value.values, [k]: v } })
  return (
    <div className="max-w-2xl space-y-5">
      <p className="text-sm text-charcoal-600">
        How long WSF keeps personal data before the daily maintenance job removes or reduces it. Changes are audited.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(value.rules).map(([key, rule]) => (
          <NumberField key={key} id={`ret-${key}`} text={`${rule.label} (${rule.unit})`}
            hint={`Default ${rule.default}; allowed ${rule.min}–${rule.max}.${key === 'unverifiedAccountDays' ? ' Not active: WSF has no email verification yet.' : ''}`}
            value={value.values[key]} onChange={set(key)} min={rule.min} max={rule.max} />
        ))}
      </div>
      <ul className="list-disc pl-5 text-xs text-charcoal-600">
        {Object.entries(value.fixed).map(([key, f]) => <li key={key}>{f.label}: {f.value} days (fixed)</li>)}
      </ul>
      <button type="button" disabled={saving} className="btn-primary disabled:opacity-60" onClick={() => save({ values: value.values })}>
        {saving ? 'Saving…' : 'Save retention periods'}
      </button>
    </div>
  )
}
