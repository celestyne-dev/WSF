import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { cancelDeletionWithLink } from '../api/accountPrivacy'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

// The "changed your mind?" link in the deletion email. Works signed out.
export default function AccountDeletionCancelPage() {
  const { token } = useParams()
  const [state, setState] = useState('working')
  useSeo({ title: 'Cancel account deletion | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    let active = true
    cancelDeletionWithLink(token).then((res) => active && setState(res.success ? 'done' : 'invalid'))
    return () => {
      active = false
    }
  }, [token])

  return (
    <div>
      <PageHeader eyebrow="Account" title="Account deletion" />
      <div className="container-editorial max-w-lg py-16 text-center" role="status" aria-live="polite">
        {state === 'working' && <p className="text-charcoal-600">Cancelling the deletion…</p>}
        {state === 'done' && (
          <div>
            <CheckCircle2 size={40} aria-hidden="true" className="mx-auto text-emerald-600" />
            <p className="mt-4 text-lg font-semibold text-charcoal">Your account will not be deleted.</p>
            <p className="mt-2 text-sm text-charcoal-600"><Link to="/login" className="font-semibold text-burgundy-600 hover:underline">Sign in</Link> to carry on.</p>
          </div>
        )}
        {state === 'invalid' && (
          <div>
            <XCircle size={40} aria-hidden="true" className="mx-auto text-rose-500" />
            <p className="mt-4 text-lg font-semibold text-charcoal">This link isn’t valid any more.</p>
            <p className="mt-2 text-sm text-charcoal-600">If your account still exists, you can cancel by <Link to="/login" className="font-semibold text-burgundy-600 hover:underline">signing in</Link>.</p>
          </div>
        )}
      </div>
    </div>
  )
}
