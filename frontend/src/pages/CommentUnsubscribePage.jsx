import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { unsubscribeReplyEmails } from '../api/comments'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

// The link in every comment-reply email. Works signed out; safe to open
// again (already unsubscribed is still a success).
export default function CommentUnsubscribePage() {
  const { token } = useParams()
  const [state, setState] = useState('working')
  useSeo({ title: 'Reply emails | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    let active = true
    unsubscribeReplyEmails(token).then((res) => active && setState(res.success ? 'done' : 'invalid'))
    return () => {
      active = false
    }
  }, [token])

  return (
    <div>
      <PageHeader eyebrow="Comments" title="Reply emails" />
      <div className="container-editorial max-w-lg py-16 text-center" role="status" aria-live="polite">
        {state === 'working' && <p className="text-charcoal-600">Processing your request…</p>}
        {state === 'done' && (
          <div>
            <CheckCircle2 size={40} aria-hidden="true" className="mx-auto text-emerald-600" />
            <p className="mt-4 text-lg font-semibold text-charcoal">You won’t get emails about replies to your comments any more.</p>
            <p className="mt-2 text-sm text-charcoal-600">You can turn them back on under any article’s comment form.</p>
          </div>
        )}
        {state === 'invalid' && (
          <div>
            <XCircle size={40} aria-hidden="true" className="mx-auto text-rose-500" />
            <p className="mt-4 text-lg font-semibold text-charcoal">This unsubscribe link isn’t valid.</p>
            <p className="mt-2 text-sm text-charcoal-600">
              <Link to="/" className="font-semibold text-burgundy-600 hover:underline">Back to Women Shaping Futures</Link>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
