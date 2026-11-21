import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { X } from 'lucide-react'
import {
  acceptAllConsent, configureConsentVersion, consentSnapshot, onConsentChange, onOpenConsentManager,
  rejectOptionalConsent, saveConsent,
} from '../../utils/consent'
import { clearAnalyticsStorage } from '../../utils/analytics'
import useDialogFocus from '../../hooks/useDialogFocus'

const DEFAULT_TITLE = 'We use cookies'
const DEFAULT_BODY =
  'We use essential technologies to make WSF work. With your permission, we may also use analytics and marketing technologies to understand how the site is used and improve our content.'

const CATEGORIES = [
  ['preferences', 'Preferences', 'Remember optional choices that make the site more convenient.'],
  ['analytics', 'Analytics', 'WSF’s own measurement of how pages and features are used (for example which links are clicked), to improve the site.'],
  ['marketing', 'Marketing', 'Third-party content that may set its own cookies, such as embedded video players. Without it, videos load only when you press play.'],
]

// First-party consent banner + "Manage choices" dialog. The banner is a
// fixed overlay (no layout shift) shown only while no valid choice exists
// for the current consent version. Accept and Reject have equal weight.
export default function CookieConsent() {
  const config = useSelector((s) => s.site.settings?.cookieConsent)
  const [snap, setSnap] = useState(consentSnapshot)
  const [managerOpen, setManagerOpen] = useState(false)

  useEffect(() => {
    if (config?.version) configureConsentVersion(config.version)
  }, [config?.version])

  useEffect(
    () =>
      onConsentChange((next) => {
        setSnap(next)
        // Withdrawal takes effect at once: stop and forget analytics data.
        if (!next.analytics) clearAnalyticsStorage()
      }),
    [],
  )
  useEffect(() => onOpenConsentManager(() => setManagerOpen(true)), [])

  const showBanner = Boolean(config?.version) && config.bannerEnabled !== false && !snap.decided && !managerOpen

  return (
    <>
      {showBanner && (
        <section
          role="region"
          aria-labelledby="cookie-banner-title"
          className="fixed inset-x-0 bottom-0 z-[60] p-3 sm:p-4"
        >
          <div className="mx-auto max-w-5xl rounded-surface border border-taupe-300 bg-ivory p-4 shadow-card sm:p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <h2 id="cookie-banner-title" className="font-serif text-lg font-semibold text-charcoal">
                  {config.title || DEFAULT_TITLE}
                </h2>
                <p className="mt-1 text-sm leading-relaxed text-charcoal-700">
                  {config.body || DEFAULT_BODY}{' '}
                  <Link to="/cookies" className="font-semibold text-burgundy-600 underline underline-offset-2">
                    Cookie Policy
                  </Link>
                </p>
              </div>
              <div className="grid shrink-0 grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                <button type="button" onClick={() => rejectOptionalConsent()} className="btn-primary !px-4 !py-2.5">
                  Reject optional
                </button>
                <button type="button" onClick={() => acceptAllConsent()} className="btn-primary !px-4 !py-2.5">
                  Accept all
                </button>
                <button type="button" onClick={() => setManagerOpen(true)} className="btn-secondary col-span-2 !px-4 !py-2.5">
                  Manage choices
                </button>
              </div>
            </div>
          </div>
        </section>
      )}
      {managerOpen && <ConsentManager snap={snap} onClose={() => setManagerOpen(false)} />}
    </>
  )
}

function ConsentManager({ snap, onClose }) {
  const ref = useRef(null)
  const [choices, setChoices] = useState(() => ({ preferences: snap.preferences, analytics: snap.analytics, marketing: snap.marketing }))
  useDialogFocus(ref, true, onClose)

  function finish(action) {
    action()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-charcoal/50 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cookie-manager-title"
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-surface border border-taupe-300 bg-ivory p-5 shadow-card sm:max-w-lg sm:rounded-surface sm:p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id="cookie-manager-title" className="font-serif text-xl font-semibold text-charcoal">
            Privacy choices
          </h2>
          <button type="button" onClick={onClose} aria-label="Close privacy choices" className="rounded-control p-1 text-charcoal-600 hover:bg-taupe-100 hover:text-charcoal">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <p className="mt-2 text-sm text-charcoal-700">
          Choose which optional technologies WSF may use. You can change this at any time from “Cookie settings” in the footer.
        </p>
        <ul className="mt-5 divide-y divide-taupe-200 border-y border-taupe-200">
          <li className="flex items-start justify-between gap-4 py-4">
            <div>
              <p className="text-sm font-semibold text-charcoal">Essential</p>
              <p className="mt-0.5 text-xs leading-relaxed text-charcoal-600">
                Sign-in, security, checkout and remembering these choices. The site cannot work without them.
              </p>
            </div>
            <span className="shrink-0 text-xs font-semibold text-charcoal-600">Always active</span>
          </li>
          {CATEGORIES.map(([key, label, help]) => (
            <li key={key} className="flex items-start justify-between gap-4 py-4">
              <div>
                <label htmlFor={`consent-${key}`} className="text-sm font-semibold text-charcoal">{label}</label>
                <p id={`consent-${key}-help`} className="mt-0.5 text-xs leading-relaxed text-charcoal-600">{help}</p>
              </div>
              <button
                id={`consent-${key}`}
                type="button"
                role="switch"
                aria-checked={choices[key]}
                aria-describedby={`consent-${key}-help`}
                onClick={() => setChoices((c) => ({ ...c, [key]: !c[key] }))}
                className={`relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors ${choices[key] ? 'border-plum-600 bg-plum-600' : 'border-charcoal-600/60 bg-taupe-100'}`}
              >
                <span className="sr-only">{choices[key] ? 'On' : 'Off'}</span>
                <span aria-hidden="true" className={`inline-block h-4 w-4 rounded-full bg-ivory shadow transition-transform motion-reduce:transition-none ${choices[key] ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <button type="button" onClick={() => finish(() => saveConsent(choices))} className="btn-primary !px-4 !py-2.5">Save choices</button>
          <button type="button" onClick={() => finish(rejectOptionalConsent)} className="btn-secondary !px-4 !py-2.5">Reject optional</button>
          <button type="button" onClick={() => finish(acceptAllConsent)} className="btn-secondary !px-4 !py-2.5">Accept all</button>
        </div>
        <p className="mt-4 text-xs text-charcoal-600">
          Read our <Link to="/cookies" onClick={onClose} className="font-semibold text-burgundy-600 underline underline-offset-2">Cookie Policy</Link> and{' '}
          <Link to="/privacy" onClick={onClose} className="font-semibold text-burgundy-600 underline underline-offset-2">Privacy Policy</Link>.
        </p>
      </div>
    </div>
  )
}
