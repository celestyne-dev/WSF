import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { fetchAdminSettings, saveAdminSettings } from '../../api/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const TABS = ['Site Identity', 'Navigation', 'Footer', 'Newsletter', 'Media Kit', 'Integrations']

const DEFAULT_AUDIENCE = {
  linkedinFollowers: 0,
  linkedinAvgReach: 0,
  linkedinEngagementRate: 0,
  newsletterSubscribers: 0,
  monthlyWebsiteVisitors: 0,
  monthlyPageViews: 0,
  countriesReached: 0,
  audienceGeography: [],
}

export default function AdminSettings() {
  const [tab, setTab] = useState(TABS[0])
  const [siteName, setSiteName] = useState('Women Shaping Futures')
  const [tagline, setTagline] = useState('Stories, Opportunity & Growth for Women Worldwide')
  const [contactEmail, setContactEmail] = useState('hello@womenshapingfutures.org')
  const [audience, setAudience] = useState(undefined)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    fetchAdminSettings()
      .then((data) => {
        if (!active) return
        setAudience({ ...DEFAULT_AUDIENCE, ...(data.audience_stats || {}) })
        if (data.site_identity?.siteName) setSiteName(data.site_identity.siteName)
        if (data.site_identity?.tagline) setTagline(data.site_identity.tagline)
        if (data.site_identity?.contactEmail) setContactEmail(data.site_identity.contactEmail)
      })
      .catch(() => active && setError('Something went wrong loading settings. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  function updateAudience(field, value) {
    setAudience((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await saveAdminSettings({
        audience_stats: audience,
        site_identity: { siteName, tagline, contactEmail },
      })
      toast.success('Settings saved.')
    } catch {
      toast.error('Something went wrong saving settings. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (error) return <EmptyState title="Couldn't load settings" description={error} />
  if (audience === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader title="Settings" description="Site-wide configuration — identity, navigation, footer, and integrations." />

      <div className="flex gap-1 border-b border-taupe-200">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium ${tab === t ? 'border-b-2 border-burgundy-600 text-burgundy-600' : 'text-charcoal-600'}`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="max-w-xl py-6">
        {tab === 'Site Identity' && (
          <div className="space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Site name</label>
              <input value={siteName} onChange={(e) => setSiteName(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Tagline</label>
              <input value={tagline} onChange={(e) => setTagline(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Contact email</label>
              <input value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Logo</label>
              <div className="mt-1.5 flex h-20 w-40 items-center justify-center border border-dashed border-taupe-300 text-xs text-charcoal-600">Upload logo</div>
            </div>
          </div>
        )}

        {tab === 'Navigation' && (
          <p className="text-sm text-charcoal-600">
            Primary and footer navigation are managed via GET/PUT <code className="bg-taupe-100 px-1">/api/v1/admin/navigation</code> — add, rename, reorder, and hide menu items without a deploy.
          </p>
        )}

        {tab === 'Footer' && (
          <p className="text-sm text-charcoal-600">
            Footer branding, link groups, social links, the newsletter CTA copy, contact info, and copyright are managed on the dedicated{' '}
            <Link to="/admin/footer" className="font-semibold text-burgundy-600 hover:underline">
              Footer
            </Link>{' '}
            page.
          </p>
        )}

        {tab === 'Newsletter' && <p className="text-sm text-charcoal-600">Default sender name, reply-to address, and double opt-in settings for WSF Weekly.</p>}

        {tab === 'Media Kit' && (
          <div className="space-y-4">
            <p className="text-sm text-charcoal-600">
              These numbers power the Partnerships page and media kit — updating them here is the only place they need to change; nothing is hard-coded in the site.
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">LinkedIn followers</label>
                <input type="number" value={audience.linkedinFollowers} onChange={(e) => updateAudience('linkedinFollowers', Number(e.target.value))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">LinkedIn average reach / post</label>
                <input type="number" value={audience.linkedinAvgReach} onChange={(e) => updateAudience('linkedinAvgReach', Number(e.target.value))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">LinkedIn engagement rate</label>
                <input type="number" step="0.001" value={audience.linkedinEngagementRate} onChange={(e) => updateAudience('linkedinEngagementRate', Number(e.target.value))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Newsletter subscribers</label>
                <input type="number" value={audience.newsletterSubscribers} onChange={(e) => updateAudience('newsletterSubscribers', Number(e.target.value))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Monthly website visitors</label>
                <input type="number" value={audience.monthlyWebsiteVisitors} onChange={(e) => updateAudience('monthlyWebsiteVisitors', Number(e.target.value))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Monthly page views</label>
                <input type="number" value={audience.monthlyPageViews} onChange={(e) => updateAudience('monthlyPageViews', Number(e.target.value))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Countries reached</label>
                <input type="number" value={audience.countriesReached} onChange={(e) => updateAudience('countriesReached', Number(e.target.value))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
            </div>

            {audience.audienceGeography.length > 0 && (
              <div className="pt-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Audience geography (region / %)</p>
                <div className="mt-2 space-y-2">
                  {audience.audienceGeography.map((g, i) => (
                    <div key={g.region} className="flex items-center gap-3">
                      <span className="w-48 text-sm text-charcoal-600">{g.region}</span>
                      <input
                        type="number"
                        value={g.percent}
                        onChange={(e) => {
                          const next = [...audience.audienceGeography]
                          next[i] = { ...g, percent: Number(e.target.value) }
                          updateAudience('audienceGeography', next)
                        }}
                        className="w-24 border border-taupe-300 px-3 py-1.5 text-sm focus:border-burgundy-500 focus:outline-none"
                      />
                      <span className="text-sm text-charcoal-600">%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'Integrations' && (
          <div className="space-y-4">
            <p className="text-sm text-charcoal-600">Analytics and tracking IDs are configurable here — never hard-coded in the frontend.</p>
            {['Google Analytics ID', 'Google Search Console', 'Meta Pixel ID', 'LinkedIn Insight Tag'].map((label) => (
              <div key={label}>
                <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</label>
                <input placeholder="Not connected" className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm text-charcoal-600/50 focus:border-burgundy-500 focus:outline-none" />
              </div>
            ))}
          </div>
        )}

        <button type="button" onClick={handleSave} disabled={saving} className="btn-primary mt-6 disabled:opacity-60">
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </div>
  )
}
