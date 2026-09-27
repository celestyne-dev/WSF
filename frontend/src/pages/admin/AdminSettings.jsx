import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { fetchAdminSettings, saveAdminSettings } from '../../api/admin'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import MediaPicker from '../../components/cms/MediaPicker'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { mapMediaRef } from '../../utils/media'

const TABS = ['Site Identity', 'Navigation', 'Footer', 'Newsletter', 'Media Kit', 'Integrations']

const DEFAULT_IDENTITY = {
  siteName: 'Women Shaping Futures',
  shortName: '',
  tagline: '',
  contactEmail: '',
  seoDefaultTitle: '',
  seoDefaultDescription: '',
}

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
  const [identity, setIdentity] = useState(DEFAULT_IDENTITY)
  const [logoMedia, setLogoMedia] = useState(null)
  const [ogImageMedia, setOgImageMedia] = useState(null)
  const [audience, setAudience] = useState(undefined)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [savingIdentity, setSavingIdentity] = useState(false)

  useEffect(() => {
    let active = true
    fetchAdminSettings()
      .then((data) => {
        if (!active) return
        setAudience({ ...DEFAULT_AUDIENCE, ...(data.audience_stats || {}) })
        const savedIdentity = data.site_identity || {}
        setIdentity({
          siteName: savedIdentity.siteName || DEFAULT_IDENTITY.siteName,
          shortName: savedIdentity.shortName || '',
          tagline: savedIdentity.tagline || '',
          contactEmail: savedIdentity.contactEmail || '',
          seoDefaultTitle: savedIdentity.seoDefaultTitle || '',
          seoDefaultDescription: savedIdentity.seoDefaultDescription || '',
        })
        setLogoMedia(mapMediaRef(savedIdentity.logo))
        setOgImageMedia(mapMediaRef(savedIdentity.ogImage))
      })
      .catch(() => active && setError('Something went wrong loading settings. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  function updateAudience(field, value) {
    setAudience((prev) => ({ ...prev, [field]: value }))
  }

  function updateIdentity(field, value) {
    setIdentity((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await saveAdminSettings({ audience_stats: audience })
      toast.success('Settings saved.')
    } catch {
      toast.error('Something went wrong saving settings. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveIdentity() {
    setSavingIdentity(true)
    try {
      const saved = await saveAdminSettings({
        site_identity: {
          ...identity,
          logoMediaId: logoMedia?.id ?? null,
          ogImageMediaId: ogImageMedia?.id ?? null,
        },
      })
      const savedIdentity = saved.site_identity || {}
      setIdentity({
        siteName: savedIdentity.siteName || DEFAULT_IDENTITY.siteName,
        shortName: savedIdentity.shortName || '',
        tagline: savedIdentity.tagline || '',
        contactEmail: savedIdentity.contactEmail || '',
        seoDefaultTitle: savedIdentity.seoDefaultTitle || '',
        seoDefaultDescription: savedIdentity.seoDefaultDescription || '',
      })
      setLogoMedia(mapMediaRef(savedIdentity.logo))
      setOgImageMedia(mapMediaRef(savedIdentity.ogImage))
      toast.success('Site identity saved.')
    } catch (err) {
      const message = err?.response?.data?.error?.message
      toast.error(message || 'Something went wrong saving site identity. Please try again.')
    } finally {
      setSavingIdentity(false)
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
          <div className="space-y-6">
            <div className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-500">Site identity</p>
              <div>
                <label htmlFor="settings-site-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Site name
                </label>
                <input
                  id="settings-site-name"
                  value={identity.siteName}
                  onChange={(e) => updateIdentity('siteName', e.target.value)}
                  maxLength={80}
                  required
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
                <p className="mt-1 text-xs text-charcoal-500">
                  The public name of the site — used in the header, footer copyright, and page titles.
                </p>
              </div>
              <div>
                <label htmlFor="settings-short-name" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Short name (optional)
                </label>
                <input
                  id="settings-short-name"
                  value={identity.shortName}
                  onChange={(e) => updateIdentity('shortName', e.target.value)}
                  maxLength={40}
                  placeholder="WSF"
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="settings-tagline" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Tagline (optional)
                </label>
                <input
                  id="settings-tagline"
                  value={identity.tagline}
                  onChange={(e) => updateIdentity('tagline', e.target.value)}
                  maxLength={160}
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Public site URL</p>
                <p className="mt-1.5 text-sm text-charcoal-600">
                  Configured via the server's <code className="bg-taupe-100 px-1">FRONTEND_URL</code> environment
                  variable, not editable here — an incorrect domain would break routing and CORS, so this stays
                  environment-controlled.
                </p>
              </div>
            </div>

            <div className="space-y-4 border-t border-taupe-200 pt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-500">Branding</p>
              <MediaPicker label="Logo" aspect={3 / 1} value={logoMedia} onChange={setLogoMedia} />
              <MediaPicker label="Default social-sharing image" aspect={1.91 / 1} value={ogImageMedia} onChange={setOgImageMedia} />
            </div>

            <div className="space-y-4 border-t border-taupe-200 pt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-500">Public contact</p>
              <div>
                <label htmlFor="settings-contact-email" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Contact email (optional)
                </label>
                <input
                  id="settings-contact-email"
                  type="email"
                  value={identity.contactEmail}
                  onChange={(e) => updateIdentity('contactEmail', e.target.value)}
                  placeholder="hello@womenshapingfutures.org"
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
                <p className="mt-1 text-xs text-charcoal-500">
                  A genuinely public address only — never a personal or internal staff email.
                </p>
              </div>
            </div>

            <div className="space-y-4 border-t border-taupe-200 pt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-500">Social profiles</p>
              <p className="text-sm text-charcoal-600">
                Real LinkedIn/Instagram/etc. profile URLs are managed on the dedicated{' '}
                <Link to="/admin/footer" className="font-semibold text-burgundy-600 hover:underline">
                  Footer
                </Link>{' '}
                page (one editable URL per platform) — Site Settings and the public site both read that same list,
                so there's never a second, conflicting copy of a profile URL.
              </p>
            </div>

            <div className="space-y-4 border-t border-taupe-200 pt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-500">SEO defaults</p>
              <div>
                <label htmlFor="settings-seo-title" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Default page title (optional)
                </label>
                <input
                  id="settings-seo-title"
                  value={identity.seoDefaultTitle}
                  onChange={(e) => updateIdentity('seoDefaultTitle', e.target.value)}
                  maxLength={70}
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
                <p className="mt-1 text-xs text-charcoal-500">
                  Fallback only — a page or article's own SEO title always takes priority over this.
                </p>
              </div>
              <div>
                <label htmlFor="settings-seo-description" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                  Default meta description (optional)
                </label>
                <textarea
                  id="settings-seo-description"
                  value={identity.seoDefaultDescription}
                  onChange={(e) => updateIdentity('seoDefaultDescription', e.target.value)}
                  maxLength={300}
                  rows={3}
                  className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>
            </div>

            <button type="button" onClick={handleSaveIdentity} disabled={savingIdentity} className="btn-primary disabled:opacity-60">
              {savingIdentity ? 'Saving…' : 'Save site identity'}
            </button>
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

        {tab === 'Media Kit' && (
          <button type="button" onClick={handleSave} disabled={saving} className="btn-primary mt-6 disabled:opacity-60">
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        )}
      </div>
    </div>
  )
}
