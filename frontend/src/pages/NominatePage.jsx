import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { submitNomination } from '../api/nominations'
import { fetchTopics, fetchSeries } from '../api/taxonomies'
import { withAcquisitionMetadata, trackEvent } from '../utils/analytics'
import { NOMINEE_AWARENESS_VALUES, NOMINEE_AWARENESS_LABELS } from '../constants/nominations'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import CountrySelect from '../components/ui/CountrySelect'

function initialForm() {
  return {
    nomineeName: '', countryCode: '', city: '', professionalTitle: '', organizationName: '',
    websiteUrl: '', linkedinUrl: '', shortBio: '',
    nominationSummary: '', achievements: '', whySignificant: '', whoImpacted: '',
    supportingLinks: [], topicSlugs: [], seriesId: '',
    isSelfNomination: false,
    nominatorName: '', nominatorEmail: '', nominatorOrganization: '', relationshipToNominee: '',
    nomineeAwareness: 'unknown',
    consentAccuracyConfirmed: false, consentReviewGiven: false, consentContactGiven: false,
    newsletterOptIn: false,
  }
}

export default function NominatePage() {
  const [form, setForm] = useState(initialForm)
  const [topics, setTopics] = useState([])
  const [series, setSeries] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(null)
  const [started, setStarted] = useState(false)

  useSeo({
    title: 'Nominate a Woman | Women Shaping Futures',
    description: 'Nominate a woman making meaningful impact in leadership, business, career, community, or beyond — Women Shaping Futures features nominees from around the world.',
    canonical: 'https://womenshapingfutures.org/nominate',
  })

  useEffect(() => {
    fetchTopics().then(setTopics).catch(() => {})
    fetchSeries().then(setSeries).catch(() => {})
    trackEvent('nomination_page_view')
  }, [])

  function markStarted() {
    if (!started) {
      setStarted(true)
      trackEvent('nomination_start')
    }
  }

  function setField(field, value) {
    markStarted()
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function toggleTopic(slug) {
    markStarted()
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  function addLink() {
    setForm((prev) => ({ ...prev, supportingLinks: [...prev.supportingLinks, { url: '', label: '' }] }))
  }

  function updateLink(index, field, value) {
    setForm((prev) => ({
      ...prev,
      supportingLinks: prev.supportingLinks.map((l, i) => (i === index ? { ...l, [field]: value } : l)),
    }))
  }

  function removeLink(index) {
    setForm((prev) => ({ ...prev, supportingLinks: prev.supportingLinks.filter((_, i) => i !== index) }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentAccuracyConfirmed || !form.consentReviewGiven || !form.consentContactGiven) {
      toast.error('Please confirm all required permissions before submitting.')
      return
    }

    setSubmitting(true)
    trackEvent('nomination_submit')
    const result = await submitNomination(withAcquisitionMetadata(form))
    setSubmitting(false)
    if (result.success) {
      trackEvent('nomination_success')
      setSubmitted(result)
    } else {
      toast.error(result.message)
    }
  }

  if (submitted) {
    return (
      <div className="container-editorial flex min-h-[50vh] flex-col items-center justify-center py-16 text-center">
        <p className="eyebrow">Nomination received</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">Thank you for the nomination</h1>
        <p className="mt-3 max-w-md text-charcoal-600">{submitted.message}</p>
        <p className="mt-2 max-w-md text-xs text-charcoal-600/70">Reference: {submitted.reference}</p>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="Nominate"
        title="Nominate a Woman"
        description="Women Shaping Futures features women making meaningful impact worldwide — in leadership, business, careers, workplaces, entrepreneurship, community, education, and beyond. Nomination doesn't guarantee recognition, but our editorial team reviews every nomination."
      />

      <div className="container-editorial max-w-2xl py-14">
        <div className="mb-8 space-y-3 border border-taupe-200 bg-taupe-50 p-5 text-sm text-charcoal-600">
          <p><strong className="text-charcoal">Who can be nominated:</strong> any woman making meaningful impact — leaders, founders, career changers, community organizers, and more, from any country.</p>
          <p><strong className="text-charcoal">Who can nominate:</strong> anyone, including the nominee herself.</p>
          <p><strong className="text-charcoal">What happens next:</strong> our editorial team reviews every nomination. We can't guarantee recognition or a specific response time.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">About the nominee</p>
          <input required placeholder="Nominee's full name" value={form.nomineeName} onChange={(e) => setField('nomineeName', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <CountrySelect required value={form.countryCode} onChange={(countryCode) => setField('countryCode', countryCode)} placeholder="Nominee's country" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <input placeholder="City (optional)" value={form.city} onChange={(e) => setField('city', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <input placeholder="Professional title / role (optional)" value={form.professionalTitle} onChange={(e) => setField('professionalTitle', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <input placeholder="Organization / company (optional)" value={form.organizationName} onChange={(e) => setField('organizationName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <input type="url" placeholder="Website or LinkedIn (optional)" value={form.websiteUrl} onChange={(e) => setField('websiteUrl', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <textarea placeholder="Short biography or context (optional)" rows={2} value={form.shortBio} onChange={(e) => setField('shortBio', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />

          <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Why you are nominating her</p>
          <input placeholder="Nomination title / summary (optional)" value={form.nominationSummary} onChange={(e) => setField('nominationSummary', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <textarea required placeholder="What has she done? What are her key achievements?" rows={5} value={form.achievements} onChange={(e) => setField('achievements', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <textarea placeholder="Why is this significant? (optional)" rows={2} value={form.whySignificant} onChange={(e) => setField('whySignificant', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <textarea placeholder="Who has been impacted? (optional)" rows={2} value={form.whoImpacted} onChange={(e) => setField('whoImpacted', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />

          {topics.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Topics (optional)</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {topics.map((t) => (
                  <button key={t.slug} type="button" onClick={() => toggleTopic(t.slug)} className={`px-2.5 py-1 text-xs font-medium ${form.topicSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
                    {t.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {series.length > 0 && (
            <select value={form.seriesId} onChange={(e) => setField('seriesId', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              <option value="">Suggest a series (optional — our editors make the final call)</option>
              {series.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Supporting links (optional)</p>
            <div className="mt-2 space-y-2">
              {form.supportingLinks.map((link, i) => (
                <div key={i} className="flex gap-2">
                  <input type="url" placeholder="https://…" value={link.url} onChange={(e) => updateLink(i, 'url', e.target.value)} className="flex-1 border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
                  <input placeholder="Label (optional)" value={link.label} onChange={(e) => updateLink(i, 'label', e.target.value)} className="w-40 border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
                  <button type="button" onClick={() => removeLink(i)} className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600">Remove</button>
                </div>
              ))}
              <button type="button" onClick={addLink} className="text-xs font-semibold text-burgundy-600 hover:underline">+ Add a supporting link</button>
            </div>
          </div>

          <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">About the nominator</p>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input type="checkbox" checked={form.isSelfNomination} onChange={(e) => setField('isSelfNomination', e.target.checked)} className="mt-1" />
            I am nominating myself
          </label>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <input required placeholder="Your name" value={form.nominatorName} onChange={(e) => setField('nominatorName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <input required type="email" placeholder="Your email" value={form.nominatorEmail} onChange={(e) => setField('nominatorEmail', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          {!form.isSelfNomination && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <input placeholder="Your organization / role (optional)" value={form.nominatorOrganization} onChange={(e) => setField('nominatorOrganization', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <input placeholder="Your relationship to the nominee (optional)" value={form.relationshipToNominee} onChange={(e) => setField('relationshipToNominee', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
          )}
          {!form.isSelfNomination && (
            <select value={form.nomineeAwareness} onChange={(e) => setField('nomineeAwareness', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              {NOMINEE_AWARENESS_VALUES.map((v) => (
                <option key={v} value={v}>{NOMINEE_AWARENESS_LABELS[v]}</option>
              ))}
            </select>
          )}

          <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Permissions</p>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input required type="checkbox" checked={form.consentAccuracyConfirmed} onChange={(e) => setField('consentAccuracyConfirmed', e.target.checked)} className="mt-1" />
            The information I've provided is accurate to the best of my knowledge.
          </label>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input required type="checkbox" checked={form.consentReviewGiven} onChange={(e) => setField('consentReviewGiven', e.target.checked)} className="mt-1" />
            I give Women Shaping Futures permission to review this nomination.
          </label>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input required type="checkbox" checked={form.consentContactGiven} onChange={(e) => setField('consentContactGiven', e.target.checked)} className="mt-1" />
            I give Women Shaping Futures permission to contact me about this nomination.
          </label>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input type="checkbox" checked={form.newsletterOptIn} onChange={(e) => setField('newsletterOptIn', e.target.checked)} className="mt-1" />
            Also subscribe me to the Women Shaping Futures newsletter
          </label>

          <button type="submit" disabled={submitting} className="btn-primary disabled:opacity-60">
            {submitting ? 'Submitting…' : 'Submit nomination'}
          </button>
          <p className="text-xs text-charcoal-600/70">
            Submitting a nomination doesn't guarantee recognition or publication. Our editorial team reviews every nomination and may follow up if we need more information.
          </p>
        </form>
      </div>
    </div>
  )
}
