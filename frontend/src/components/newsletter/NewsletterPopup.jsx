import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { X } from 'lucide-react'
import { subscribeToNewsletter } from '../../api/newsletter'
import NewsletterConsent from './NewsletterConsent'
import { withAcquisitionMetadata } from '../../utils/analytics'
import { consentSnapshot, hasConsent, onConsentChange } from '../../utils/consent'
import {
  isPopupExcludedPath, isPopupSuppressed, popupStorageFor, popupTriggerReached, readPopupState, scrollPercentOf, writePopupState,
} from '../../utils/newsletterPopup'
import useDialogFocus from '../../hooks/useDialogFocus'

const DEFAULTS = { enabled: true, delaySeconds: 15, scrollPercent: 45, dismissDays: 14, successDays: 365, title: 'WSF Weekly',
  body: 'Career moves, opportunities and women worth knowing, delivered to your inbox.', ctaLabel: 'Join WSF Weekly' }

// localStorage only with Preferences consent, otherwise sessionStorage
// (utils/newsletterPopup.js popupStorageFor).
function store() {
  try {
    return popupStorageFor(hasConsent('preferences'), { local: window.localStorage, session: window.sessionStorage })
  } catch {
    return null
  }
}

// Time on the site counts from the first public page view of this visit.
const visitStart = typeof performance !== 'undefined' ? performance.now() : 0

// WSF Weekly signup popup, using the existing newsletter subscribe API (one
// subscriber list; placement "newsletter-popup"). Opens once per page load
// after the configured time on site OR scroll depth, never on excluded
// routes, never while the cookie banner still needs an answer, and not again
// after a close (cooldown) or a signup (success period).
export default function NewsletterPopup() {
  const configured = useSelector((s) => s.site.settings?.newsletterPopup)
  const settings = configured ? { ...DEFAULTS, ...configured } : null
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [consentDecided, setConsentDecided] = useState(() => consentSnapshot().decided)
  const fired = useRef(false)

  useEffect(() => onConsentChange((snap) => setConsentDecided(snap.decided)), [])
  const bannerPending = useSelector((s) => s.site.settings?.cookieConsent?.bannerEnabled !== false) && !consentDecided

  const eligible = Boolean(settings?.enabled) && !isPopupExcludedPath(pathname) && !bannerPending
  useEffect(() => {
    if (!eligible || fired.current || isPopupSuppressed(readPopupState(store()), settings)) return undefined
    const check = () => {
      if (fired.current) return
      if (popupTriggerReached({ elapsedMs: performance.now() - visitStart, scrollPercent: scrollPercentOf() }, settings)) {
        fired.current = true
        setOpen(true)
      }
    }
    const timer = window.setInterval(check, 1000)
    window.addEventListener('scroll', check, { passive: true })
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('scroll', check)
    }
    // settings is rebuilt each render from the same stored values; its fields are the real inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eligible, settings?.delaySeconds, settings?.scrollPercent, settings?.dismissDays, settings?.successDays])

  // Leaving for an excluded route closes it without counting as a dismissal.
  useEffect(() => {
    if (open && isPopupExcludedPath(pathname)) setOpen(false)
  }, [open, pathname])

  if (!open || !settings) return null
  return <PopupDialog settings={settings} onClose={() => setOpen(false)} />
}

function PopupDialog({ settings, onClose }) {
  const ref = useRef(null)
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [status, setStatus] = useState('idle') // idle | sending | done | error
  const [message, setMessage] = useState('')

  const dismiss = useCallback(() => {
    if (status !== 'done') writePopupState(store(), { ...readPopupState(store()), dismissedAt: new Date().toISOString() })
    onClose()
  }, [status, onClose])
  useDialogFocus(ref, true, dismiss, 'input[type="email"]')

  async function submit(e) {
    e.preventDefault()
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setStatus('error')
      setMessage('Enter a valid email address.')
      return
    }
    if (!consent) {
      setStatus('error')
      setMessage('Please tick the box to agree to receive the newsletter.')
      return
    }
    setStatus('sending')
    const result = await subscribeToNewsletter(withAcquisitionMetadata({ email: email.trim(), placement: 'newsletter-popup', consent: true }))
    if (result.success) {
      writePopupState(store(), { ...readPopupState(store()), subscribedAt: new Date().toISOString() })
      setStatus('done')
      setMessage('')
    } else {
      setStatus('error')
      setMessage(result.message || 'Something went wrong. Please try again.')
    }
  }

  return (
    <div className="fixed inset-0 z-[65] flex items-end justify-center bg-charcoal/40 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && dismiss()}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="newsletter-popup-title"
        aria-describedby="newsletter-popup-body"
        className="relative w-full rounded-t-surface border border-taupe-300 bg-ivory px-5 pb-6 pt-5 shadow-card sm:max-w-md sm:rounded-surface sm:p-7"
      >
        <button type="button" onClick={dismiss} aria-label="Close newsletter signup" className="absolute right-3 top-3 rounded-control p-1.5 text-charcoal-600 hover:bg-taupe-100 hover:text-charcoal">
          <X size={18} aria-hidden="true" />
        </button>
        {status === 'done' ? (
          <div role="status" className="pr-8">
            {/* Neutral on purpose: the subscribe API answers the same way for
                every address (no list-state disclosure), so this never promises
                delivery. */}
            <h2 id="newsletter-popup-title" className="font-serif text-2xl font-semibold text-charcoal">Check your inbox.</h2>
            <p id="newsletter-popup-body" className="mt-2 text-sm text-charcoal-700">If this address isn’t already on {settings.title}, we’ve sent a link to confirm your subscription. Nothing is sent until you confirm.</p>
            <button type="button" onClick={onClose} className="btn-secondary mt-5 !px-4 !py-2.5">Close</button>
          </div>
        ) : (
          <>
            <p className="eyebrow">Newsletter</p>
            <h2 id="newsletter-popup-title" className="mt-2 pr-8 font-serif text-2xl font-semibold leading-tight text-charcoal">{settings.title}</h2>
            <p id="newsletter-popup-body" className="mt-2 text-sm leading-relaxed text-charcoal-700">{settings.body}</p>
            <form onSubmit={submit} noValidate className="mt-5 flex flex-col gap-2.5">
              <label htmlFor="newsletter-popup-email" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Email address</label>
              <input
                id="newsletter-popup-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={status === 'error'}
                aria-describedby={status === 'error' ? 'newsletter-popup-error' : undefined}
                className="rounded-control w-full border border-taupe-300 bg-white px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
              />
              <NewsletterConsent id="newsletter-popup-consent" checked={consent} onChange={setConsent} />
              {status === 'error' && <p id="newsletter-popup-error" role="alert" className="text-xs font-medium text-rose-700">{message}</p>}
              <button type="submit" disabled={status === 'sending'} className="btn-primary w-full disabled:opacity-60">
                {status === 'sending' ? 'Joining…' : settings.ctaLabel}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
