import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { confirmNewsletterSubscription } from '../api/newsletter'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

// The double opt-in link in the confirmation email. Opening the link does
// nothing by itself: the person presses the button, which posts the token,
// so a mail scanner that opens (or even renders) links can't confirm.
export default function NewsletterConfirmPage() {
  const { token } = useParams()
  const [state, setState] = useState({ phase: 'ready' })
  useSeo({ title: 'Confirm your subscription | Women Shaping Futures', robots: 'noindex, nofollow' })

  async function confirm() {
    setState({ phase: 'working' })
    const res = await confirmNewsletterSubscription(token)
    if (res.success) return setState({ phase: res.result === 'review_required' ? 'review' : 'done' })
    return setState({ phase: res.code === 'confirmation_expired' ? 'expired' : 'invalid' })
  }

  return (
    <div>
      <PageHeader eyebrow="Newsletter" title="WSF Weekly" />
      <div className="container-editorial max-w-lg py-16 text-center" role="status" aria-live="polite">
        {(state.phase === 'ready' || state.phase === 'working') && (
          <div>
            <p className="text-charcoal-600">Press the button to confirm you’d like to receive WSF Weekly by email.</p>
            <button type="button" onClick={confirm} disabled={state.phase === 'working'} className="btn-primary mt-6 disabled:opacity-60">
              {state.phase === 'working' ? 'Confirming…' : 'Confirm my subscription'}
            </button>
          </div>
        )}
        {state.phase === 'review' && (
          <p className="text-charcoal-600">
            Thanks, your confirmation is recorded. Earlier emails to this address bounced or were reported, so our team will
            check delivery before we send WSF Weekly again.
          </p>
        )}
        {state.phase === 'done' && (
          <div>
            <CheckCircle2 size={40} aria-hidden="true" className="mx-auto text-emerald-600" />
            <p className="mt-4 text-lg font-semibold text-charcoal">You’re subscribed to WSF Weekly.</p>
            <p className="mt-2 text-sm text-charcoal-600">Every issue has a link to unsubscribe. <Link to="/privacy" className="font-semibold text-burgundy-600 hover:underline">Privacy Policy</Link></p>
          </div>
        )}
        {(state.phase === 'expired' || state.phase === 'invalid') && (
          <div>
            <XCircle size={40} aria-hidden="true" className="mx-auto text-rose-500" />
            <p className="mt-4 text-lg font-semibold text-charcoal">
              {state.phase === 'expired' ? 'This confirmation link has expired.' : 'This confirmation link isn’t valid.'}
            </p>
            <p className="mt-2 text-sm text-charcoal-600">
              You can <Link to="/newsletter" className="font-semibold text-burgundy-600 hover:underline">sign up again</Link> to get a new link.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
