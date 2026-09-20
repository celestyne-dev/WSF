import { useState } from 'react'
import { toast } from 'react-toastify'
import AdminPageHeader from '../../components/cms/AdminPageHeader'

const TABS = ['Site Identity', 'Navigation', 'Footer', 'Newsletter', 'Integrations']

export default function AdminSettings() {
  const [tab, setTab] = useState(TABS[0])
  const [siteName, setSiteName] = useState('Women Shaping Futures')
  const [tagline, setTagline] = useState('Stories, Opportunity & Growth for Women Worldwide')
  const [contactEmail, setContactEmail] = useState('hello@womenshapingfutures.org')

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
            Primary and footer navigation are managed here in production — add, rename, reorder, and hide menu items without a deploy. See{' '}
            <code className="bg-taupe-100 px-1">src/mock/navigation.js</code> for the data shape this screen edits.
          </p>
        )}

        {tab === 'Footer' && <p className="text-sm text-charcoal-600">Footer link groups, social links, and the newsletter CTA copy are configured here.</p>}

        {tab === 'Newsletter' && <p className="text-sm text-charcoal-600">Default sender name, reply-to address, and double opt-in settings for WSF Weekly.</p>}

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

        <button type="button" onClick={() => toast.success('Settings saved.')} className="btn-primary mt-6">
          Save changes
        </button>
      </div>
    </div>
  )
}
