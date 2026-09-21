import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { Download } from 'lucide-react'
import { submitPartnershipInquiry, fetchAudienceStats } from '../api/site'
import { withAcquisitionMetadata, trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

const fmt = (n) => new Intl.NumberFormat('en-US').format(n)

function buildFormats(stats) {
  return [
    { title: 'Sponsored Editorial', description: 'A commissioned story or profile, clearly labeled, written in our editorial voice.' },
    { title: 'Sponsored Series', description: 'Co-brand an ongoing series like Founder Stories with your organization.' },
    { title: 'Newsletter Sponsorship', description: `A dedicated placement in WSF Weekly, reaching ${fmt(stats.newsletterSubscribers)}+ engaged subscribers.` },
    { title: 'Social Media Campaigns', description: `Custom content across our ${fmt(stats.linkedinFollowers)}+ follower LinkedIn audience.` },
    { title: 'Employer Branding', description: 'Featured job placements and employer profile pages for talent attraction.' },
    { title: 'Event Sponsorship', description: 'Brand presence at the Women in Leadership Summit and WSF webinars.' },
    { title: 'Sponsored Resources', description: 'Co-branded guides, templates, and worksheets in our resource library.' },
    { title: 'Research Partnerships', description: 'Co-commissioned reports and original research on women in business.' },
  ]
}

export default function PartnershipsPage() {
  const [form, setForm] = useState({ company: '', contactName: '', email: '', interest: 'Sponsored editorial content', message: '' })
  const [submitting, setSubmitting] = useState(false)
  const [audienceStats, setAudienceStats] = useState(null)

  useEffect(() => {
    let active = true
    fetchAudienceStats()
      .then((data) => active && setAudienceStats(data))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: 'Partnerships | Women Shaping Futures',
    description: 'Partner with Women Shaping Futures on sponsored content, events, newsletter placements, and more.',
    canonical: 'https://womenshapingfutures.org/partnerships',
  })

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    const result = await submitPartnershipInquiry(withAcquisitionMetadata(form))
    setSubmitting(false)
    if (result.success) {
      trackEvent('partnership_inquiry_submitted', { interest: form.interest })
      toast.success(result.message)
      setForm({ company: '', contactName: '', email: '', interest: 'Sponsored editorial content', message: '' })
    }
  }

  const stats = audienceStats
    ? [
        { label: 'LinkedIn followers', value: `${fmt(audienceStats.linkedinFollowers)}+` },
        { label: 'Newsletter subscribers', value: `${fmt(audienceStats.newsletterSubscribers)}+` },
        { label: 'Monthly page views', value: `${fmt(audienceStats.monthlyPageViews)}+` },
        { label: 'Countries reached', value: `${audienceStats.countriesReached}` },
      ]
    : []
  const formats = buildFormats(audienceStats || { newsletterSubscribers: 0, linkedinFollowers: 0 })

  return (
    <div>
      <PageHeader eyebrow="Partnerships" title="Reach Women Shaping the Future" description="Partner with a trusted editorial platform read by ambitious, career-driven women around the world, with particularly strong readership in the United States.">
        <a href="#media-kit" className="btn-primary mt-6 inline-flex" onClick={() => trackEvent('media_kit_request_click')}>
          <Download size={16} /> Request our media kit
        </a>
      </PageHeader>

      <div className="container-editorial py-14">
        {stats.length > 0 && (
          <div className="grid grid-cols-2 gap-6 border-b border-taupe-200 pb-14 sm:grid-cols-4">
            {stats.map((s) => (
              <div key={s.label} className="text-center">
                <p className="font-serif text-3xl font-semibold text-burgundy-600 sm:text-4xl">{s.value}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-charcoal-600">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        {audienceStats && (
          <div className="grid grid-cols-1 gap-10 border-b border-taupe-200 py-14 sm:grid-cols-3">
            <div>
              <h3 className="font-serif text-lg font-semibold text-charcoal">Audience Geography</h3>
              <ul className="mt-4 space-y-2">
                {(audienceStats.audienceGeography || []).map((g) => (
                  <li key={g.region} className="flex items-center justify-between text-sm text-charcoal-600">
                    <span>{g.region}</span>
                    <span className="font-semibold text-charcoal">{g.percent}%</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-serif text-lg font-semibold text-charcoal">Audience Industries</h3>
              <ul className="mt-4 space-y-2">
                {(audienceStats.audienceIndustries || []).map((g) => (
                  <li key={g.name} className="flex items-center justify-between text-sm text-charcoal-600">
                    <span>{g.name}</span>
                    <span className="font-semibold text-charcoal">{g.percent}%</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-serif text-lg font-semibold text-charcoal">Audience Seniority</h3>
              <ul className="mt-4 space-y-2">
                {(audienceStats.audienceSeniority || []).map((g) => (
                  <li key={g.level} className="flex items-center justify-between text-sm text-charcoal-600">
                    <span>{g.level}</span>
                    <span className="font-semibold text-charcoal">{g.percent}%</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <div className="py-14">
          <h2 className="font-serif text-3xl font-semibold text-charcoal">Available Partnership Formats</h2>
          <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {formats.map((f) => (
              <div key={f.title} className="border border-taupe-200 bg-white p-5">
                <h3 className="font-serif text-lg font-semibold text-charcoal">{f.title}</h3>
                <p className="mt-2 text-sm text-charcoal-600">{f.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div id="media-kit" className="grid grid-cols-1 gap-10 border-t border-taupe-200 py-14 lg:grid-cols-2">
          <div>
            <h2 className="font-serif text-2xl font-semibold text-charcoal">Let's talk</h2>
            <p className="mt-3 text-base text-charcoal-600">
              Tell us about your goals and our partnerships team will respond within two business days with a media kit and proposal.
            </p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <input required placeholder="Company name" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <input required placeholder="Contact name" value={form.contactName} onChange={(e) => setForm({ ...form, contactName: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <input required type="email" placeholder="Work email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <select value={form.interest} onChange={(e) => setForm({ ...form, interest: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              {formats.map((f) => (
                <option key={f.title}>{f.title}</option>
              ))}
            </select>
            <textarea required placeholder="Tell us about your goals" rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <button type="submit" disabled={submitting} className="btn-primary w-full disabled:opacity-60">
              {submitting ? 'Sending…' : 'Send inquiry'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
