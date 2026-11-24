import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { ArrowRight } from 'lucide-react'
import { subscribe, resetNewsletterStatus } from '../../features/newsletter/newsletterSlice'
import { withAcquisitionMetadata } from '../../utils/analytics'
import NewsletterConsent from '../newsletter/NewsletterConsent'

export default function NewsletterForm({ variant = 'light', source = 'inline', buttonLabel = 'Subscribe' }) {
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const dispatch = useDispatch()
  const status = useSelector((s) => s.newsletter.status)

  const isDark = variant === 'dark'

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email.includes('@')) {
      toast.error('Please enter a valid email address.')
      return
    }
    if (!consent) {
      toast.error('Please tick the box to agree to receive the newsletter.')
      return
    }
    const result = await dispatch(
      subscribe(withAcquisitionMetadata({ email, placement: source, consent: true })),
    )
    if (result.meta.requestStatus === 'fulfilled' && result.payload.success) {
      toast.success(result.payload.message)
      setEmail('')
      setConsent(false)
      dispatch(resetNewsletterStatus())
    } else {
      toast.error(result.payload?.message || 'Something went wrong. Please try again.')
      dispatch(resetNewsletterStatus())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-md" noValidate>
      <div className="flex flex-col gap-3 sm:flex-row">
      <label htmlFor={`newsletter-email-${source}`} className="sr-only">
        Email address
      </label>
      <input
        id={`newsletter-email-${source}`}
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Your email address"
        className={`rounded-control w-full flex-1 border px-4 py-3 text-sm focus:outline-none ${
          isDark
            ? 'border-ivory/30 bg-transparent text-ivory placeholder:text-ivory/60 focus:border-ivory'
            : 'border-taupe-300 bg-white text-charcoal placeholder:text-charcoal-600/60 focus:border-burgundy-500'
        }`}
      />
      <button
        type="submit"
        disabled={status === 'loading'}
        className={`rounded-control inline-flex shrink-0 items-center justify-center gap-2 px-6 py-3 text-sm font-semibold transition-colors disabled:opacity-60 ${
          isDark ? 'bg-ivory text-charcoal hover:bg-blush-100' : 'bg-plum-600 text-ivory hover:bg-plum-700'
        }`}
      >
        {status === 'loading' ? 'Subscribing…' : buttonLabel}
        <ArrowRight size={16} />
      </button>
      </div>
      <div className="mt-2.5">
        <NewsletterConsent id={`newsletter-consent-${source}`} checked={consent} onChange={setConsent} dark={isDark} />
      </div>
    </form>
  )
}
