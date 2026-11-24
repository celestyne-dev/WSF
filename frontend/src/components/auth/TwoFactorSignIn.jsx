import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { confirmTwoFactorSetup, startTwoFactorSetup, submitTwoFactorChallenge } from '../../api/twoFactor'
import { mapUser } from '../../api/auth'
import { signedIn } from '../../features/auth/authSlice'
import { CodeField, RecoveryCodes, TwoFactorQr } from './TwoFactorParts'

// The second sign-in step after a correct password (backend
// app/services/two_factor.py). mode "challenge": enter a code or a recovery
// code. mode "setup": the account's role requires 2FA and it isn't set up
// yet, so it is set up now; finishing signs the member in. No session exists
// until this step succeeds.
export default function TwoFactorSignIn({ step, onSignedIn, onCancel }) {
  const dispatch = useDispatch()
  const [code, setCode] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [setup, setSetup] = useState(null)
  const [codes, setCodes] = useState(null)
  const [pendingUser, setPendingUser] = useState(null)

  useEffect(() => {
    if (step.mode !== 'setup') return undefined
    let active = true
    startTwoFactorSetup({ token: step.token }).then((res) => {
      if (!active) return
      if (res.success) setSetup(res.data)
      else setError(res.message)
    })
    return () => {
      active = false
    }
  }, [step])

  function finish(data) {
    const user = mapUser(data.user)
    dispatch(signedIn({ user, accessToken: data.access_token }))
    return user
  }

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    if (step.mode === 'challenge') {
      const res = await submitTwoFactorChallenge(useRecovery ? { token: step.token, recoveryCode: code } : { token: step.token, code })
      setBusy(false)
      if (!res.success) return setError(res.message)
      return onSignedIn(finish(res.data), res.data.recovery_codes_remaining)
    }
    const res = await confirmTwoFactorSetup({ token: step.token, code })
    setBusy(false)
    if (!res.success) return setError(res.message)
    setPendingUser(finish(res.data))
    setCodes(res.data.recovery_codes)
    return undefined
  }

  if (codes) {
    return (
      <div className="space-y-4">
        <h2 className="font-serif text-xl font-semibold text-charcoal">Two-factor authentication is on</h2>
        <RecoveryCodes codes={codes} onDone={() => onSignedIn(pendingUser)} />
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4" aria-describedby="two-factor-help">
      <h2 className="font-serif text-xl font-semibold text-charcoal">
        {step.mode === 'setup' ? 'Set up two-factor authentication' : 'Two-factor authentication'}
      </h2>
      <p id="two-factor-help" className="text-sm text-charcoal-700">
        {step.mode === 'setup'
          ? 'Your WSF role requires a second step at sign-in. Set it up once now; it takes about a minute.'
          : useRecovery
            ? 'Enter one of the recovery codes you saved when you set this up. Each code works once.'
            : 'Enter the 6-digit code from your authenticator app.'}
      </p>
      {step.mode === 'setup' && !setup && !error && <p className="text-sm text-charcoal-600">Preparing your set-up code…</p>}
      {step.mode === 'setup' && setup && <TwoFactorQr setup={setup} />}
      {useRecovery ? (
        <div>
          <label htmlFor="recovery-code" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Recovery code</label>
          <input id="recovery-code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" required
            className="mt-1.5 w-full border border-taupe-300 px-4 py-3 font-mono text-sm focus:border-burgundy-500 focus:outline-none" />
        </div>
      ) : (
        <CodeField id="two-factor-code" value={code} onChange={setCode} />
      )}
      {error && <p role="alert" className="text-sm text-burgundy-600">{error}</p>}
      <button type="submit" disabled={busy || (step.mode === 'setup' && !setup)} className="btn-primary w-full disabled:opacity-60">
        {busy ? 'Checking…' : step.mode === 'setup' ? 'Turn on and sign in' : 'Verify and sign in'}
      </button>
      <div className="flex flex-wrap justify-between gap-2 text-xs">
        {step.mode === 'challenge' && (
          <button type="button" onClick={() => { setUseRecovery(!useRecovery); setCode(''); setError(null) }} className="font-semibold text-burgundy-600 hover:underline">
            {useRecovery ? 'Use my authenticator app instead' : 'Use a recovery code'}
          </button>
        )}
        <button type="button" onClick={onCancel} className="font-semibold text-charcoal-600 hover:underline">Back to sign in</button>
      </div>
    </form>
  )
}
