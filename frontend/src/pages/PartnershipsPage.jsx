import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { Download } from 'lucide-react'
import { fetchAudienceStats } from '../api/site'
import { submitPartnershipInquiry } from '../api/partnerships'
import { fetchCountries } from '../api/geography'
import { withAcquisitionMetadata, trackEvent } from '../utils/analytics'
import { PARTNERSHIP_TYPES } from '../constants/partnerships'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

const fmt = (n) => new Intl.NumberFormat('en-US').format(n)

function blankForm() {
  return {
    contactName: '',
    email: '',
    phone: '',
    jobTitle: '',
    company: '',
    website: '',
    countryCode: '',
    partnershipType: PARTNERSHIP_TYPES[0],
    subject: '',
    message: '',
    goals: '',
    proposedTiming: '',
    budgetRange: '',
    consentGiven: false,
  }
}

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
  const [form, setForm] = useState(blankForm())
  const [submitting, setSubmitting] = useState(false)
  const [audienceStats, setAudienceStats] = useState(null)
  const [countries, setCountries] = useState([])

  useEffect(() => {
    let active = true
    fetchAudienceStats()
      .then((data) => active && setAudienceStats(data))
      .catch(() => {})
    fetchCountries()
      .then((list) => active && setCountries([...list].sort((a, b) => a.name.localeCompare(b.name))))
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
    if (!form.consentGiven) {
      toast.error('Please confirm we may use your submitted information to respond.')
      return
    }
    setSubmitting(true)
    const result = await submitPartnershipInquiry(withAcquisitionMetadata(form))
    setSubmitting(false)
    if (result.success) {
      trackEvent('partnership_inquiry_submitted', { partnershipType: form.partnershipType })
      toast.success(result.message)
      setForm(blankForm())
    } else {
      toast.error(result.message)
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
              Tell us about your organization and what you have in mind. Our team reviews every partnership inquiry and will follow up from there.
            </p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Contact</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="pf-contactName">Contact name</label>
              <input id="pf-contactName" required placeholder="Contact name" value={form.contactName} onChange={(e) => setForm({ ...form, contactName: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="pf-email">Work email</label>
              <input id="pf-email" required type="email" placeholder="Work email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="pf-phone">Phone (optional)</label>
              <input id="pf-phone" type="tel" placeholder="Phone (optional)" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="pf-jobTitle">Job title (optional)</label>
              <input id="pf-jobTitle" placeholder="Job title (optional)" value={form.jobTitle} onChange={(e) => setForm({ ...form, jobTitle: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>

            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Organization</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="pf-company">Organization name</label>
              <input id="pf-company" required placeholder="Organization name" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="pf-website">Website (optional)</label>
              <input id="pf-website" type="url" placeholder="Website (optional)" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <label className="sr-only" htmlFor="pf-country">Country / region (optional)</label>
            <select id="pf-country" value={form.countryCode} onChange={(e) => setForm({ ...form, countryCode: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              <option value="">Country / region (optional)</option>
              {countries.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>

            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Your inquiry</p>
            <label className="sr-only" htmlFor="pf-type">Partnership type</label>
            <select id="pf-type" value={form.partnershipType} onChange={(e) => setForm({ ...form, partnershipType: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              {PARTNERSHIP_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <label className="sr-only" htmlFor="pf-subject">Subject / short title</label>
            <input id="pf-subject" placeholder="Subject / short title" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <label className="sr-only" htmlFor="pf-message">Tell us about your idea</label>
            <textarea id="pf-message" required placeholder="Tell us about your idea" rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <label className="sr-only" htmlFor="pf-goals">Goals / objectives (optional)</label>
            <textarea id="pf-goals" placeholder="Goals / objectives (optional)" rows={3} value={form.goals} onChange={(e) => setForm({ ...form, goals: e.target.value })} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="pf-timing">Proposed timing (optional)</label>
              <input id="pf-timing" placeholder="Proposed timing (optional, e.g. Q1 2027)" value={form.proposedTiming} onChange={(e) => setForm({ ...form, proposedTiming: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="pf-budget">Estimated budget range (optional)</label>
              <input id="pf-budget" placeholder="Estimated budget range (optional)" value={form.budgetRange} onChange={(e) => setForm({ ...form, budgetRange: e.target.value })} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>

            <label className="flex items-start gap-2 text-sm text-charcoal-600">
              <input
                required
                type="checkbox"
                checked={form.consentGiven}
                onChange={(e) => setForm({ ...form, consentGiven: e.target.checked })}
                className="mt-0.5"
              />
              I confirm the information above may be used by Women Shaping Futures to respond to this inquiry.
            </label>

            <button type="submit" disabled={submitting} className="btn-primary w-full disabled:opacity-60">
              {submitting ? 'Sending…' : 'Send inquiry'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
