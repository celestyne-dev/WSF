import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import useSeo from '../hooks/useSeo'
import {
  confirmTwoFactorSetup, disableTwoFactor, fetchTwoFactorStatus, regenerateRecoveryCodes, startTwoFactorSetup,
} from '../api/twoFactor'
import { CodeField, RecoveryCodes, TwoFactorQr } from '../components/auth/TwoFactorParts'

// Password (the form itself lives only at /change-password, also used for
// the forced-change flow) and two-factor authentication. 2FA is optional
// for members and required for some staff roles (backend
// app/services/two_factor.py); a required account can't turn it off here.
export default function AccountSecurityPage() {
  useSeo({ title: 'Security | Women Shaping Futures', robots: 'noindex, nofollow' })

  return (
    <div className="max-w-[720px] space-y-10">
      <section>
        <h2 className="font-serif text-2xl font-semibold text-charcoal">Security</h2>
        <p className="mt-2 text-sm text-charcoal-600">
          You can change the password you use to sign in to your WSF account at any time.
        </p>
        <Link to="/change-password" className="btn-primary mt-6 inline-block">
          Change password
        </Link>
      </section>
      <TwoFactorSection />
    </div>
  )
}

function TwoFactorSection() {
  const [status, setStatus] = useState(null)
  const [mode, setMode] = useState(null) // 'setup' | 'codes' | 'disable' | 'show-codes'
  const [setup, setSetup] = useState(null)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [codes, setCodes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function reload() {
    fetchTwoFactorStatus().then(setStatus).catch(() => setError('Could not load your two-factor settings.'))
  }
  useEffect(reload, [])

  function reset() {
    setMode(null); setSetup(null); setCode(''); setPassword(''); setError(null)
  }

  async function beginSetup() {
    setError(null)
    const res = await startTwoFactorSetup()
    if (!res.success) return setError(res.message)
    setSetup(res.data)
    setMode('setup')
    return undefined
  }

  async function run(action) {
    setBusy(true)
    setError(null)
    const res = await action()
    setBusy(false)
    return res
  }

  async function confirm(e) {
    e.preventDefault()
    const res = await run(() => confirmTwoFactorSetup({ code }))
    if (!res.success) return setError(res.message)
    setCodes(res.data.recovery_codes)
    setMode('show-codes')
    return undefined
  }

  async function newCodes(e) {
    e.preventDefault()
    const res = await run(() => regenerateRecoveryCodes({ code }))
    if (!res.success) return setError(res.message)
    setCodes(res.codes)
    setMode('show-codes')
    return undefined
  }

  async function turnOff(e) {
    e.preventDefault()
    const res = await run(() => disableTwoFactor({ password, code }))
    if (!res.success) return setError(res.message)
    toast.success('Two-factor authentication is off.')
    reset()
    reload()
    return undefined
  }

  if (!status) {
    return <section aria-busy="true"><p className="text-sm text-charcoal-600">{error || 'Loading two-factor settings…'}</p></section>
  }

  return (
    <section aria-labelledby="two-factor-heading">
      <h2 id="two-factor-heading" className="font-serif text-2xl font-semibold text-charcoal">Two-factor authentication</h2>
      <p className="mt-2 text-sm text-charcoal-600">
        {status.enabled
          ? `On. Signing in asks for a code from your authenticator app. ${status.recoveryCodesRemaining} recovery code${status.recoveryCodesRemaining === 1 ? '' : 's'} left.`
          : 'Off. Add a second step at sign-in: a 6-digit code from an authenticator app on your phone.'}
        {status.required && ' Your WSF role requires it.'}
      </p>
      {error && <p role="alert" className="mt-3 text-sm text-burgundy-600">{error}</p>}

      {mode === 'show-codes' && codes && (
        <div className="mt-6 max-w-md">
          <RecoveryCodes codes={codes} doneLabel="Done" onDone={() => { setCodes(null); reset(); reload() }} />
        </div>
      )}

      {mode === 'setup' && setup && (
        <form onSubmit={confirm} className="mt-6 max-w-md space-y-4">
          <TwoFactorQr setup={setup} />
          <CodeField id="setup-code" value={code} onChange={setCode} />
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="btn-primary disabled:opacity-60">{busy ? 'Checking…' : 'Turn on'}</button>
            <button type="button" onClick={reset} className="btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {mode === 'codes' && (
        <form onSubmit={newCodes} className="mt-6 max-w-md space-y-4">
          <p className="text-sm text-charcoal-700">Your current recovery codes will stop working.</p>
          <CodeField id="codes-code" value={code} onChange={setCode} />
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="btn-primary disabled:opacity-60">Create new codes</button>
            <button type="button" onClick={reset} className="btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {mode === 'disable' && (
        <form onSubmit={turnOff} className="mt-6 max-w-md space-y-4">
          <div>
            <label htmlFor="disable-password" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Password</label>
            <input id="disable-password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required
              className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <CodeField id="disable-code" value={code} onChange={setCode} />
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="btn-primary disabled:opacity-60">Turn off</button>
            <button type="button" onClick={reset} className="btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {!mode && (
        <div className="mt-6 flex flex-wrap gap-2">
          {!status.enabled && <button type="button" onClick={beginSetup} className="btn-primary">Turn on two-factor authentication</button>}
          {status.enabled && <button type="button" onClick={() => setMode('codes')} className="btn-secondary">Create new recovery codes</button>}
          {status.enabled && !status.required && <button type="button" onClick={() => setMode('disable')} className="btn-secondary">Turn off</button>}
        </div>
      )}
    </section>
  )
}
