import useSettingsSection from '../../hooks/useSettingsSection'

// Studio -> Settings -> Integrations. Bare provider IDs only (validated
// again server-side: backend app/services/tracking_settings.py). Each
// integration is OFF until its ID is saved, and even then runs only for
// visitors who consented to its category.

const input = 'rounded-control w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none sm:w-72'
const label = 'text-xs font-semibold uppercase tracking-wide text-charcoal-600'

export default function TrackingSettingsPanel() {
  const { value, setValue, error, saving, save } = useSettingsSection('tracking')
  if (error) return <p className="text-sm text-burgundy-600">{error}</p>
  if (!value) return <p className="text-sm text-charcoal-600">Loading…</p>
  const set = (k) => (e) => setValue({ ...value, [k]: e.target.value })
  return (
    <div className="max-w-2xl space-y-6">
      <p className="text-sm text-charcoal-600">
        Each integration stays off until you enter its ID here. Once set, it still only runs for visitors who allowed its cookie
        category, and stops when they withdraw. Only the ID is stored: no script or code can be added.
      </p>
      <div>
        <label htmlFor="trk-ga4" className={label}>Google Analytics 4 Measurement ID</label>
        <input id="trk-ga4" value={value.ga4MeasurementId || ''} onChange={set('ga4MeasurementId')} placeholder="G-XXXXXXXXXX" maxLength={22} className={`${input} mt-1.5`} aria-describedby="trk-ga4-help" />
        <p id="trk-ga4-help" className="mt-1 text-xs text-charcoal-600">
          Needs Analytics consent. Consent Mode v2 starts with every signal denied; Google Signals and advertising features stay
          off. Withdrawing consent stops measurement and deletes the site’s _ga cookies. {value.ga4MeasurementId ? 'Status: configured.' : 'Status: off.'}
        </p>
      </div>
      <div>
        <label htmlFor="trk-linkedin" className={label}>LinkedIn Insight Tag Partner ID</label>
        <input id="trk-linkedin" value={value.linkedinPartnerId || ''} onChange={set('linkedinPartnerId')} placeholder="1234567" inputMode="numeric" maxLength={12} className={`${input} mt-1.5`} aria-describedby="trk-linkedin-help" />
        <p id="trk-linkedin-help" className="mt-1 text-xs text-charcoal-600">
          Needs Marketing consent, and never runs while a visitor’s browser sends Global Privacy Control. {value.linkedinPartnerId ? 'Status: configured.' : 'Status: off.'}
        </p>
      </div>
      <div>
        <label htmlFor="trk-meta" className={label}>Meta Pixel ID</label>
        <input id="trk-meta" value={value.metaPixelId || ''} onChange={set('metaPixelId')} placeholder="123456789012345" inputMode="numeric" maxLength={20} className={`${input} mt-1.5`} aria-describedby="trk-meta-help" />
        <p id="trk-meta-help" className="mt-1 text-xs text-charcoal-600">
          Needs Marketing consent, and never runs with Global Privacy Control. Automatic collection of button and page details is off.
          Withdrawing consent revokes it and deletes the site’s _fbp / _fbc cookies. {value.metaPixelId ? 'Status: configured.' : 'Status: off.'}
        </p>
      </div>
      <div>
        <span className={label}>Google Search Console</span>
        <input disabled placeholder="Not available yet" aria-label="Google Search Console (not available yet)" className={`${input} mt-1.5 text-charcoal-600/50`} />
      </div>
      <button type="button" onClick={() => save({
        ga4MeasurementId: (value.ga4MeasurementId || '').trim(),
        linkedinPartnerId: (value.linkedinPartnerId || '').trim(),
        metaPixelId: (value.metaPixelId || '').trim(),
      })} disabled={saving} className="btn-primary disabled:opacity-60">
        {saving ? 'Saving…' : 'Save integrations'}
      </button>
    </div>
  )
}
