import { useState } from 'react'

const input = 'w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none'

/** Six-digit code field (one-time codes autofill on supporting devices). */
export function CodeField({ id, value, onChange, label = 'Code from your authenticator app' }) {
  return (
    <div>
      <label htmlFor={id} className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/[^\d ]/g, '').slice(0, 7))}
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9 ]*"
        required
        className={`${input} mt-1.5 tracking-[0.3em]`}
      />
    </div>
  )
}

/** Step 1 of set-up: scan the QR code, or type the key by hand. */
export function TwoFactorQr({ setup }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-charcoal-700">
        Scan this QR code with an authenticator app (for example Google Authenticator, Microsoft Authenticator or 1Password).
      </p>
      <img src={setup.qrSvg} alt="QR code for your authenticator app" width="184" height="184" className="mx-auto block border border-taupe-200 bg-white p-2" />
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Can’t scan it? Enter this key</p>
        <code className="mt-1 block break-all border border-taupe-200 bg-cream px-3 py-2 text-sm tracking-wider text-charcoal">
          {setup.secret.match(/.{1,4}/g).join(' ')}
        </code>
      </div>
    </div>
  )
}

/** Recovery codes, shown once. The member must confirm before continuing. */
export function RecoveryCodes({ codes, onDone, doneLabel = 'Continue' }) {
  const [saved, setSaved] = useState(false)
  const text = codes.join('\n')
  return (
    <div className="space-y-4">
      <p className="text-sm text-charcoal-700">
        Save these recovery codes somewhere safe. Each one works once if you lose access to your authenticator app. They
        won’t be shown again.
      </p>
      <ul className="grid grid-cols-2 gap-2 border border-taupe-200 bg-cream p-3 font-mono text-sm text-charcoal" aria-label="Recovery codes">
        {codes.map((c) => <li key={c}>{c}</li>)}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary !px-4 !py-2" onClick={() => navigator.clipboard?.writeText(text)}>Copy codes</button>
        <a
          className="btn-secondary !px-4 !py-2"
          href={`data:text/plain;charset=utf-8,${encodeURIComponent(`Women Shaping Futures recovery codes\n\n${text}\n`)}`}
          download="wsf-recovery-codes.txt"
        >
          Download
        </a>
      </div>
      <label className="flex items-start gap-2 text-sm text-charcoal-700">
        <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} className="mt-1" />
        I’ve saved my recovery codes.
      </label>
      <button type="button" disabled={!saved} onClick={onDone} className="btn-primary w-full disabled:opacity-60">{doneLabel}</button>
    </div>
  )
}
