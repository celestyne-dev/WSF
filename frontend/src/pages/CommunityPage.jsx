import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { fetchPublicCommunity, joinCommunity } from '../api/community'
import { fetchCountries } from '../api/geography'
import { fetchTopics } from '../api/taxonomies'
import { fetchEvents } from '../api/events'
import { withAcquisitionMetadata, trackEvent } from '../utils/analytics'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'

function blankForm() {
  return {
    firstName: '',
    lastName: '',
    email: '',
    countryCode: '',
    interestSlugs: [],
    professionalTitle: '',
    organizationName: '',
    linkedinUrl: '',
    websiteUrl: '',
    shortBio: '',
    referralNote: '',
    consentGiven: false,
    subscribeNewsletter: false,
  }
}

export default function CommunityPage() {
  const [data, setData] = useState(undefined)
  const [notAvailable, setNotAvailable] = useState(false)
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [events, setEvents] = useState([])
  const [form, setForm] = useState(blankForm())
  const [submitting, setSubmitting] = useState(false)
  const [startedJoin, setStartedJoin] = useState(false)

  useEffect(() => {
    let active = true
    fetchPublicCommunity()
      .then((res) => {
        if (!active) return
        setData(res)
        trackEvent('community_page_view')
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotAvailable(true)
        setData(null)
      })
    fetchCountries().then((list) => active && setCountries([...list].sort((a, b) => a.name.localeCompare(b.name)))).catch(() => {})
    fetchTopics().then((list) => active && setTopics(list)).catch(() => {})
    fetchEvents({ dateFrom: new Date().toISOString().slice(0, 10), pageSize: 3 })
      .then((res) => active && setEvents(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: data?.page?.seo?.title || 'Community | Women Shaping Futures',
    description:
      data?.page?.seo?.description ||
      'The Women Shaping Futures community — connect with members across industries, career stages, and countries.',
    canonical: 'https://womenshapingfutures.org/community',
    robots: data?.page?.seo?.robots,
    image: data?.page?.heroMedia?.mediaPath,
  })

  function toggleInterest(slug) {
    if (!startedJoin) {
      setStartedJoin(true)
      trackEvent('community_join_start')
    }
    setForm((prev) => ({
      ...prev,
      interestSlugs: prev.interestSlugs.includes(slug) ? prev.interestSlugs.filter((s) => s !== slug) : [...prev.interestSlugs, slug],
    }))
  }

  function handleFieldChange(field, value) {
    if (!startedJoin) {
      setStartedJoin(true)
      trackEvent('community_join_start')
    }
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentGiven) {
      toast.error('Please confirm we may use your submitted information to process your request.')
      return
    }
    setSubmitting(true)
    const result = await joinCommunity(withAcquisitionMetadata({ ...form, source: 'Community page' }))
    setSubmitting(false)
    if (result.success) {
      trackEvent('community_join_submit')
      toast.success(result.message)
      setForm(blankForm())
      setStartedJoin(false)
    } else {
      toast.error(result.message)
    }
  }

  if (data === undefined) return <PageLoader />
  if (notAvailable || data === null) {
    return (
      <EmptyState
        title="Community page unavailable"
        description="This page isn't published yet. Please check back soon."
      />
    )
  }

  const { page, metrics } = data

  return (
    <div>
      <PageHeader eyebrow="Community" title={page.heroHeading || 'The WSF Community'} description={page.heroDescription} />

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

        {metrics && (
          <div className="grid grid-cols-2 gap-6 border-b border-taupe-200 py-14 sm:grid-cols-2">
            <div className="text-center">
              <p className="font-serif text-3xl font-semibold text-burgundy-600 sm:text-4xl">
                {new Intl.NumberFormat('en-US').format(metrics.memberCount)}+
              </p>
              <p className="mt-1 text-xs uppercase tracking-wide text-charcoal-600">Members</p>
            </div>
            <div className="text-center">
              <p className="font-serif text-3xl font-semibold text-burgundy-600 sm:text-4xl">{metrics.countryCount}</p>
              <p className="mt-1 text-xs uppercase tracking-wide text-charcoal-600">Countries represented</p>
            </div>
          </div>
        )}

        {page.benefits?.length > 0 && (
          <div className="border-b border-taupe-200 py-14">
            <h2 className="font-serif text-3xl font-semibold text-charcoal">Why join</h2>
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {page.benefits.map((b, i) => (
                <div key={i} className="border border-taupe-200 bg-white p-5">
                  <h3 className="font-serif text-lg font-semibold text-charcoal">{b.title}</h3>
                  {b.description && <p className="mt-2 text-sm text-charcoal-600">{b.description}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {(page.whoForText || page.howToJoinText) && (
          <div className="grid grid-cols-1 gap-10 border-b border-taupe-200 py-14 sm:grid-cols-2">
            {page.whoForText && (
              <div>
                <h3 className="font-serif text-lg font-semibold text-charcoal">Who it's for</h3>
                <p className="mt-2 text-sm text-charcoal-600">{page.whoForText}</p>
              </div>
            )}
            {page.howToJoinText && (
              <div>
                <h3 className="font-serif text-lg font-semibold text-charcoal">How to join</h3>
                <p className="mt-2 text-sm text-charcoal-600">{page.howToJoinText}</p>
              </div>
            )}
          </div>
        )}

        {events.length > 0 && (
          <div className="border-b border-taupe-200 py-14">
            <div className="flex items-center justify-between">
              <h2 className="font-serif text-3xl font-semibold text-charcoal">Upcoming events</h2>
              <Link to="/events" className="text-sm font-semibold text-burgundy-600 hover:underline">
                See all events &rarr;
              </Link>
            </div>
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
              {events.map((ev) => (
                <Link key={ev.id} to={`/events/${ev.slug}`} className="block border border-taupe-200 bg-white p-5 hover:border-burgundy-400">
                  <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">{ev.date ? formatDate(ev.date) : ''}</p>
                  <h3 className="mt-1 font-serif text-lg font-semibold text-charcoal">{ev.title}</h3>
                </Link>
              ))}
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

        <div id="join" className="grid grid-cols-1 gap-10 border-t border-taupe-200 py-14 lg:grid-cols-2">
          <div>
            <h2 className="font-serif text-2xl font-semibold text-charcoal">{page.ctaHeading || 'Join the community'}</h2>
            <p className="mt-3 text-base text-charcoal-600">{page.ctaDescription || 'Tell us a bit about yourself and we will be in touch.'}</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">About you</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="cf-firstName">First name</label>
              <input id="cf-firstName" required placeholder="First name" value={form.firstName} onChange={(e) => handleFieldChange('firstName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="cf-lastName">Last name</label>
              <input id="cf-lastName" required placeholder="Last name" value={form.lastName} onChange={(e) => handleFieldChange('lastName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <label className="sr-only" htmlFor="cf-email">Email</label>
            <input id="cf-email" required type="email" placeholder="Email address" value={form.email} onChange={(e) => handleFieldChange('email', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <label className="sr-only" htmlFor="cf-country">Country</label>
            <select id="cf-country" required value={form.countryCode} onChange={(e) => handleFieldChange('countryCode', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              <option value="">Select your country…</option>
              {countries.map((c) => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </select>

            {topics.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Interests</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {topics.map((t) => (
                    <button
                      key={t.slug}
                      type="button"
                      onClick={() => toggleInterest(t.slug)}
                      className={`px-2.5 py-1 text-xs font-medium ${form.interestSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Optional</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sr-only" htmlFor="cf-title">Professional title</label>
              <input id="cf-title" placeholder="Professional title (optional)" value={form.professionalTitle} onChange={(e) => handleFieldChange('professionalTitle', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="cf-org">Organization</label>
              <input id="cf-org" placeholder="Organization / company (optional)" value={form.organizationName} onChange={(e) => handleFieldChange('organizationName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
            <label className="sr-only" htmlFor="cf-linkedin">LinkedIn</label>
            <input id="cf-linkedin" type="url" placeholder="LinkedIn or website (optional)" value={form.linkedinUrl} onChange={(e) => handleFieldChange('linkedinUrl', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <label className="sr-only" htmlFor="cf-bio">A short introduction</label>
            <textarea id="cf-bio" placeholder="A short introduction — what you hope to gain or contribute (optional)" rows={3} value={form.shortBio} onChange={(e) => handleFieldChange('shortBio', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <label className="sr-only" htmlFor="cf-referral">How did you hear about us?</label>
            <input id="cf-referral" placeholder="How did you hear about us? (optional)" value={form.referralNote} onChange={(e) => handleFieldChange('referralNote', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />

            <label className="flex items-start gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.subscribeNewsletter} onChange={(e) => handleFieldChange('subscribeNewsletter', e.target.checked)} className="mt-0.5" />
              Also subscribe me to the Women Shaping Futures newsletter
            </label>

            <label className="flex items-start gap-2 text-sm text-charcoal-600">
              <input required type="checkbox" checked={form.consentGiven} onChange={(e) => handleFieldChange('consentGiven', e.target.checked)} className="mt-0.5" />
              I confirm the information above may be used by Women Shaping Futures to process this request.
            </label>

            <button type="submit" disabled={submitting} className="btn-primary w-full disabled:opacity-60">
              {submitting ? 'Joining…' : page.ctaButtonLabel || 'Join WSF'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
