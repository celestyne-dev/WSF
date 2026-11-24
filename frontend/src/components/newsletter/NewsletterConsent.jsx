import { Link } from 'react-router-dom'

// The one newsletter consent checkbox (backend: SubscribeResource requires
// consent === true; wording version engagement_settings
// NEWSLETTER_CONSENT_VERSION "newsletter-v2"). Unticked by default; nothing
// is sent or stored without it. Change the wording -> bump that version.
export const NEWSLETTER_CONSENT_TEXT = 'Yes, send me the WSF Weekly newsletter by email. I can unsubscribe at any time.'

export default function NewsletterConsent({ id, checked, onChange, dark = false }) {
  const text = dark ? 'text-ivory/85' : 'text-charcoal-600'
  const link = dark ? 'text-ivory underline' : 'font-semibold text-burgundy-600 hover:underline'
  return (
    <div className={`flex items-start gap-2 text-left text-xs ${text}`}>
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 shrink-0" />
      <label htmlFor={id}>
        {NEWSLETTER_CONSENT_TEXT}{' '}
        <span>We’ll email you a link to confirm. See our </span>
        <Link to="/privacy" className={link}>Privacy Policy</Link>.
      </label>
    </div>
  )
}
