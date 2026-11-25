import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { confirmEmailVerification, fetchCurrentUser, resendEmailVerification } from '../api/auth'
import { setUser } from '../features/auth/authSlice'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

// Batch 4 corrections: first-party email verification.
//  /verify-email          "check your inbox" + resend (signed in)
//  /verify-email/:token   the emailed link. Opening it does nothing until the
//                         person presses the button, so a mail scanner that
//                         opens links can't confirm on anyone's behalf.
export default function VerifyEmailPage() {
  const { token } = useParams()
  const location = useLocation()
  const dispatch = useDispatch()
  const user = useSelector((s) => s.auth.user)
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [state, setState] = useState({ phase: 'idle', message: location.state?.sendFailed ? 'We couldn’t send the email just now. Please use “Send a new link”.' : '' })
  useSeo({ title: 'Confirm your email | Women Shaping Futures', robots: 'noindex, nofollow' })

  async function confirm() {
    setState({ phase: 'working', message: '' })
    const res = await confirmEmailVerification(token)
    if (!res.success) return setState({ phase: 'failed', message: res.message })
    if (accessToken) {
      const fresh = await fetchCurrentUser(accessToken)
      if (fresh) dispatch(setUser(fresh))
    }
    return setState({ phase: 'done', message: '' })
  }

  async function resend() {
    setState({ phase: 'working', message: '' })
    const res = await resendEmailVerification()
    setState({ phase: 'idle', message: res.success ? (res.result === 'already_verified' ? 'Your email address is already confirmed.' : 'We’ve emailed you a new link. It works once, for 24 hours.') : res.message })
  }

  const link = 'font-semibold text-burgundy-600 hover:underline'
  return (
    <div>
      <PageHeader eyebrow="Your account" title="Confirm your email" />
      <div className="container-editorial max-w-lg py-12 text-center">
        {token ? (
          state.phase === 'done' ? (
            <p role="status" className="text-lg font-semibold text-charcoal">
              Your email address is confirmed. <Link to={accessToken ? '/account' : '/login'} className={link}>{accessToken ? 'Go to your account' : 'Sign in'}</Link>
            </p>
          ) : (
            <>
              <p className="text-charcoal-600">Press the button to confirm this is your email address.</p>
              <button type="button" onClick={confirm} disabled={state.phase === 'working'} className="btn-primary mt-6 disabled:opacity-60">
                {state.phase === 'working' ? 'Confirming…' : 'Confirm my email address'}
              </button>
              {state.phase === 'failed' && (
                <p role="alert" className="mt-4 text-sm text-rose-700">
                  {state.message} {accessToken ? 'You can ask for a new link below.' : <>Sign in to ask for a new link. <Link to="/login" className={link}>Sign in</Link></>}
                </p>
              )}
            </>
          )
        ) : (
          <p className="text-charcoal-600">
            {user?.email ? <>We sent a confirmation link to <strong>{user.email}</strong>.</> : 'We sent you a confirmation link.'}{' '}
            Open it and press the button to finish setting up your account. The link works for 24 hours.
          </p>
        )}
        {accessToken && state.phase !== 'done' && (!token || state.phase === 'failed') && (
          <button type="button" onClick={resend} disabled={state.phase === 'working'} className="btn-secondary mt-6 disabled:opacity-60">
            Send a new link
          </button>
        )}
        <p role="status" aria-live="polite" className="mt-4 text-sm text-charcoal-600">{state.message}</p>
      </div>
    </div>
  )
}
