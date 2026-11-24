import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { confirmNewsletterSubscription } from '../api/newsletter'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

// The double opt-in link in the confirmation email. Posts the token (so a
// mail scanner fetching the link can't confirm on someone's behalf).
export default function NewsletterConfirmPage() {
  const { token } = useParams()
  const [state, setState] = useState({ phase: 'working' })
  useSeo({ title: 'Confirm your subscription | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    let active = true
    confirmNewsletterSubscription(token).then((res) => {
      if (!active) return
      setState(res.success ? { phase: 'done' } : { phase: res.code === 'confirmation_expired' ? 'expired' : 'invalid' })
    })
    return () => {
      active = false
    }
  }, [token])

  return (
    <div>
      <PageHeader eyebrow="Newsletter" title="WSF Weekly" />
      <div className="container-editorial max-w-lg py-16 text-center" role="status" aria-live="polite">
        {state.phase === 'working' && <p className="text-charcoal-600">Confirming your subscription…</p>}
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
