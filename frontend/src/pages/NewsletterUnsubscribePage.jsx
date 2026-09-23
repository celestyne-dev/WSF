import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { unsubscribeByToken } from '../api/newsletter'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

export default function NewsletterUnsubscribePage() {
  const { token } = useParams()
  const [result, setResult] = useState(undefined)
  const [error, setError] = useState(null)

  useSeo({ title: 'Unsubscribe | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    let active = true
    unsubscribeByToken(token)
      .then((data) => {
        if (!active) return
        setResult(data)
        trackEvent('newsletter_unsubscribe', { source: 'email_link' })
      })
      .catch(() => active && setError('This unsubscribe link is invalid or has expired.'))
    return () => {
      active = false
    }
  }, [token])

  return (
    <div>
      <PageHeader eyebrow="Newsletter" title="Unsubscribe" />
      <div className="container-editorial max-w-lg py-16 text-center">
        {result === undefined && !error && <p className="text-charcoal-600">Processing your request…</p>}
        {error && (
          <div>
            <XCircle size={40} className="mx-auto text-rose-500" />
            <p className="mt-4 text-lg font-semibold text-charcoal">{error}</p>
            <p className="mt-2 text-sm text-charcoal-600">
              If you're trying to manage your subscription, you can also{' '}
              <Link to="/newsletter" className="font-semibold text-burgundy-600 hover:underline">
                visit the newsletter page
              </Link>
              .
            </p>
          </div>
        )}
        {result && (
          <div>
            <CheckCircle2 size={40} className="mx-auto text-emerald-600" />
            <p className="mt-4 text-lg font-semibold text-charcoal">You've been unsubscribed</p>
            <p className="mt-2 text-sm text-charcoal-600">
              {result.email} will no longer receive WSF Weekly. You can resubscribe any time from the{' '}
              <Link to="/newsletter" className="font-semibold text-burgundy-600 hover:underline">
                newsletter page
              </Link>
              .
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
