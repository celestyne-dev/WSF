import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { Download } from 'lucide-react'
import { fetchPublicAdvertise } from '../api/advertise'
import { submitPartnershipInquiry } from '../api/partnerships'
import { fetchCountries } from '../api/geography'
import { withAcquisitionMetadata, trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'

function blankForm(offeringName) {
  return {
    contactName: '',
    email: '',
    phone: '',
    jobTitle: '',
    company: '',
    website: '',
    countryCode: '',
    subject: offeringName || '',
    message: '',
    goals: '',
    proposedTiming: '',
    budgetRange: '',
    consentGiven: false,
  }
}

function formatPrice(offering) {
  if (offering.pricingMode === 'hidden') return null
  if (offering.pricingMode === 'contact') return 'Contact for pricing'
  if (!offering.priceAmount) return null
  const amount = new Intl.NumberFormat('en-US').format(offering.priceAmount)
  const withCurrency = offering.currency ? `${offering.currency} ${amount}` : amount
  return offering.pricingMode === 'starting_from' ? `Starting from ${withCurrency}` : withCurrency
}

export default function AdvertisePage() {
  const [data, setData] = useState(undefined)
  const [countries, setCountries] = useState([])
  const [form, setForm] = useState(blankForm(''))
  const [submitting, setSubmitting] = useState(false)
  const [startedInquiry, setStartedInquiry] = useState(false)
  const [notAvailable, setNotAvailable] = useState(false)

  useEffect(() => {
    let active = true
    fetchPublicAdvertise()
      .then((res) => {
        if (!active) return
        setData(res)
        trackEvent('advertise_page_view')
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotAvailable(true)
        setData(null)
      })
    fetchCountries()
      .then((list) => active && setCountries([...list].sort((a, b) => a.name.localeCompare(b.name))))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: data?.page?.seo?.title || 'Advertise | Women Shaping Futures',
    description:
      data?.page?.seo?.description ||
      'Advertise and partner with Women Shaping Futures — a trusted editorial platform for ambitious, career-driven women.',
    canonical: 'https://womenshapingfutures.org/advertise',
    robots: data?.page?.seo?.robots,
    image: data?.page?.heroMedia?.mediaPath,
  })

  function handleFieldChange(field, value) {
    if (!startedInquiry) {
      setStartedInquiry(true)
      trackEvent('advertise_inquiry_start')
    }
    setForm({ ...form, [field]: value })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentGiven) {
      toast.error('Please confirm we may use your submitted information to respond.')
      return
    }
    setSubmitting(true)
    const result = await submitPartnershipInquiry(
      withAcquisitionMetadata({ ...form, partnershipType: 'Advertising' })
    )
    setSubmitting(false)
    if (result.success) {
      trackEvent('advertise_inquiry_submit')
      toast.success(result.message)
      setForm(blankForm(''))
      setStartedInquiry(false)
    } else {
      toast.error(result.message)
    }
  }

  function handleOfferingCta(offering) {
    trackEvent('offering_cta_click', { offeringId: offering.id, offeringName: offering.name })
    setForm((f) => ({ ...f, subject: offering.name }))
    document.getElementById('advertise-inquiry')?.scrollIntoView({ behavior: 'smooth' })
  }

  function handleMediaKitDownload() {
    trackEvent('media_kit_download')
  }

  if (data === undefined) return <PageLoader />
  if (notAvailable || data === null) {
    return (
      <EmptyState
        title="Advertise page unavailable"
        description="This page isn't published yet. Please check back soon, or contact us directly to discuss advertising and partnership opportunities."
      />
    )
  }

  const { page, metrics, offerings } = data

  return (
    <div>
      <PageHeader eyebrow="Advertise" title={page.heroHeading || 'Advertise With Women Shaping Futures'} description={page.heroDescription}>
        {page.mediaKit && (
          <a href={page.mediaKit.url} target="_blank" rel="noreferrer" className="btn-primary mt-6 inline-flex" onClick={handleMediaKitDownload}>
            <Download size={16} /> {page.mediaKit.title || 'Download media kit'}
          </a>
        )}
      </PageHeader>

      <div className="container-editorial py-14">
        {page.heroMedia && (
          <div className="mb-14">
            <MediaImage media={page.heroMedia} variant="large" width={1200} height={600} aspect={2} priority className="w-full object-cover" />
          </div>
        )}

        {page.introContent?.length > 0 && (
          <div className="mx-auto max-w-3xl border-b border-taupe-200 pb-14">
            <ArticleContent blocks={page.introContent} />
          </div>
        )}

        {(page.audienceOverview || metrics.length > 0) && (
          <div className="border-b border-taupe-200 py-14">
            {page.audienceOverview && <p className="mx-auto max-w-3xl text-base text-charcoal-600">{page.audienceOverview}</p>}
            {metrics.length > 0 && (
              <div className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-4">
                {metrics.map((m) => (
                  <div key={m.id} className="text-center">
                    <p className="font-serif text-3xl font-semibold text-burgundy-600 sm:text-4xl">
                      {m.value} {m.unit || ''}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-wide text-charcoal-600">{m.label}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {page.whyContent?.length > 0 && (
          <div className="mx-auto max-w-3xl border-b border-taupe-200 py-14">
            <ArticleContent blocks={page.whyContent} />
          </div>
        )}

        {offerings.length > 0 && (
          <div className="border-b border-taupe-200 py-14">
            <h2 className="font-serif text-3xl font-semibold text-charcoal">Advertising &amp; Partnership Offerings</h2>
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {offerings.map((o) => {
                const price = formatPrice(o)
                return (
                  <div key={o.id} className={`border p-5 ${o.featured ? 'border-burgundy-400 bg-blush-50' : 'border-taupe-200 bg-white'}`}>
                    {o.featured && <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</p>}
                    <h3 className="font-serif text-lg font-semibold text-charcoal">{o.name}</h3>
                    {o.shortDescription && <p className="mt-2 text-sm text-charcoal-600">{o.shortDescription}</p>}
                    {o.features?.length > 0 && (
                      <ul className="mt-3 space-y-1 text-sm text-charcoal-600">
                        {o.features.map((f, i) => (
                          <li key={i}>&bull; {f}</li>
                        ))}
                      </ul>
                    )}
                    {price && <p className="mt-3 text-sm font-semibold text-charcoal">{price}</p>}
                    {o.pricingNote && <p className="mt-1 text-xs text-charcoal-600/60">{o.pricingNote}</p>}
                    <button type="button" onClick={() => handleOfferingCta(o)} className="mt-4 text-sm font-semibold text-burgundy-600 hover:underline">
                      {o.ctaLabel || 'Enquire'} &rarr;
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {page.faq?.length > 0 && (
          <div className="border-b border-taupe-200 py-14">
            <h2 className="font-serif text-3xl font-semibold text-charcoal">Frequently Asked Questions</h2>
            <div className="mt-8 space-y-6">
              {page.faq.map((f, i) => (
                <div key={i}>
                  <h3 className="font-serif text-lg font-semibold text-charcoal">{f.question}</h3>
                  <p className="mt-1 text-sm text-charcoal-600">{f.answer}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="py-10 text-center text-xs text-charcoal-600/60">
          Advertising and sponsored content on Women Shaping Futures is always clearly disclosed and never presented as independent editorial coverage.
        </p>

        <div id="advertise-inquiry" className="grid grid-cols-1 gap-10 border-t border-taupe-200 py-14 lg:grid-cols-2">
          <div>
            <h2 className="font-serif text-2xl font-semibold text-charcoal">{page.ctaHeading || "Let's talk"}</h2>
            <p className="mt-3 text-base text-charcoal-600">{page.ctaDescription || 'Tell us about your goals and our team will follow up.'}</p>
            {(page.contactEmail || page.contactNote) && (
              <div className="mt-6 border border-taupe-200 bg-white p-5 text-sm text-charcoal-600">
                {page.contactEmail && (
                  <p>
                    Email us directly:{' '}
                    <a href={`mailto:${page.contactEmail}`} className="font-semibold text-burgundy-600 hover:underline">
                      {page.contactEmail}
                    </a>
                  </p>
                )}
                {page.contactNote && <p className="mt-2">{page.contactNote}</p>}
              </div>
            )}
          </div>
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Contact</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="af-contactName">Contact name</label>
              <input id="af-contactName" required placeholder="Contact name" value={form.contactName} onChange={(e) => handleFieldChange('contactName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="af-email">Work email</label>
              <input id="af-email" required type="email" placeholder="Work email" value={form.email} onChange={(e) => handleFieldChange('email', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="af-phone">Phone (optional)</label>
              <input id="af-phone" type="tel" placeholder="Phone (optional)" value={form.phone} onChange={(e) => handleFieldChange('phone', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="af-jobTitle">Job title (optional)</label>
              <input id="af-jobTitle" placeholder="Job title (optional)" value={form.jobTitle} onChange={(e) => handleFieldChange('jobTitle', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>

            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Organization</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="af-company">Organization name</label>
              <input id="af-company" required placeholder="Organization name" value={form.company} onChange={(e) => handleFieldChange('company', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="af-website">Website (optional)</label>
              <input id="af-website" type="url" placeholder="Website (optional)" value={form.website} onChange={(e) => handleFieldChange('website', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <label className="sr-only" htmlFor="af-country">Country / region (optional)</label>
            <select id="af-country" value={form.countryCode} onChange={(e) => handleFieldChange('countryCode', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              <option value="">Country / region (optional)</option>
              {countries.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>

            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Your campaign</p>
            <label className="sr-only" htmlFor="af-subject">What are you interested in?</label>
            <input id="af-subject" placeholder="What are you interested in? (e.g. Newsletter Sponsorship)" value={form.subject} onChange={(e) => handleFieldChange('subject', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <label className="sr-only" htmlFor="af-message">Tell us about your goals</label>
            <textarea id="af-message" required placeholder="Tell us about your goals" rows={4} value={form.message} onChange={(e) => handleFieldChange('message', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="af-timing">Proposed timing (optional)</label>
              <input id="af-timing" placeholder="Proposed timing (optional, e.g. Q1 2027)" value={form.proposedTiming} onChange={(e) => handleFieldChange('proposedTiming', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="af-budget">Estimated budget range (optional)</label>
              <input id="af-budget" placeholder="Estimated budget range (optional)" value={form.budgetRange} onChange={(e) => handleFieldChange('budgetRange', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>

            <label className="flex items-start gap-2 text-sm text-charcoal-600">
              <input
                required
                type="checkbox"
                checked={form.consentGiven}
                onChange={(e) => handleFieldChange('consentGiven', e.target.checked)}
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
