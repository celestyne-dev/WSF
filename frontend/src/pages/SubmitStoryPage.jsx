import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { submitStorySubmission, uploadSubmissionMedia } from '../api/submissions'
import { fetchTopics } from '../api/taxonomies'
import { withAcquisitionMetadata, trackEvent } from '../utils/analytics'
import { STORY_TYPES, STORY_TYPE_LABELS, CONTENT_ORIGINS, CONTENT_ORIGIN_LABELS, AI_INVOLVEMENT_VALUES, AI_INVOLVEMENT_LABELS } from '../constants/submissions'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import CountrySelect from '../components/ui/CountrySelect'

const MAX_IMAGES = 3

function initialForm() {
  return {
    firstName: '', lastName: '', email: '', countryCode: '', city: '',
    professionalTitle: '', organizationName: '', linkedinUrl: '', websiteUrl: '',
    title: '', summary: '', body: '', whyItMatters: '', keyLessons: '', storyType: '', topicSlugs: [],
    subjectIsSubmitter: true, subjectName: '', subjectRelationship: '',
    contentOrigin: '', previousPublicationUrl: '', aiInvolvement: 'none', aiProvenanceNote: '',
    media: [],
    consentReviewGiven: false, consentContactGiven: false, consentAccuracyConfirmed: false,
    consentMediaRightsConfirmed: false, newsletterOptIn: false,
  }
}

export default function SubmitStoryPage() {
  const [form, setForm] = useState(initialForm)
  const [topics, setTopics] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [uploadingMedia, setUploadingMedia] = useState(false)
  const [submitted, setSubmitted] = useState(null)
  const [started, setStarted] = useState(false)

  useSeo({
    title: 'Submit Your Story | Women Shaping Futures',
    description: 'Share your career, leadership, business, or personal story with Women Shaping Futures — submissions from women around the world are welcome.',
    canonical: 'https://womenshapingfutures.org/submit',
  })

  useEffect(() => {
    fetchTopics().then(setTopics).catch(() => {})
    trackEvent('story_submission_page_view')
  }, [])

  function markStarted() {
    if (!started) {
      setStarted(true)
      trackEvent('story_submission_start')
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

  async function handleAddImage(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || form.media.length >= MAX_IMAGES) return
    setUploadingMedia(true)
    try {
      const uploaded = await uploadSubmissionMedia(file)
      setForm((prev) => ({
        ...prev,
        media: [...prev.media, { mediaId: uploaded.id, publicUrl: uploaded.publicUrl, caption: '', credit: '', rightsConfirmed: false }],
      }))
    } catch (err) {
      toast.error(err?.apiError?.message || "We couldn't upload that image. Please try a different file.")
    } finally {
      setUploadingMedia(false)
    }
  }

  function updateMediaField(index, field, value) {
    setForm((prev) => ({
      ...prev,
      media: prev.media.map((m, i) => (i === index ? { ...m, [field]: value } : m)),
    }))
  }

  function removeMedia(index) {
    setForm((prev) => ({ ...prev, media: prev.media.filter((_, i) => i !== index) }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentReviewGiven || !form.consentContactGiven || !form.consentAccuracyConfirmed) {
      toast.error('Please confirm all required permissions before submitting.')
      return
    }
    if (!form.subjectIsSubmitter && !form.subjectName.trim()) {
      toast.error('Please tell us who this story is about.')
      return
    }
    if (form.media.length > 0 && !form.consentMediaRightsConfirmed) {
      toast.error('Please confirm you have permission to submit the attached image(s).')
      return
    }

    setSubmitting(true)
    trackEvent('story_submission_submit')
    const result = await submitStorySubmission(withAcquisitionMetadata(form))
    setSubmitting(false)
    if (result.success) {
      trackEvent('story_submission_success')
      setSubmitted(result)
    } else {
      toast.error(result.message)
    }
  }

  if (submitted) {
    return (
      <div className="container-editorial flex min-h-[50vh] flex-col items-center justify-center py-16 text-center">
        <p className="eyebrow">Thank you</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">Your story is with our editorial team</h1>
        <p className="mt-3 max-w-md text-charcoal-600">{submitted.message}</p>
        <p className="mt-2 max-w-md text-xs text-charcoal-600/70">Reference: {submitted.reference}</p>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="Submit"
        title="Submit Your Story"
        description="Women Shaping Futures publishes stories from women around the world — career journeys, leadership stories, founder stories, workplace stories, reinvention, and more. Submission doesn't guarantee publication, but our editorial team reviews every story we receive."
      />

      <div className="container-editorial max-w-2xl py-14">
        <div className="mb-8 space-y-3 border border-taupe-200 bg-taupe-50 p-5 text-sm text-charcoal-600">
          <p><strong className="text-charcoal">What we're looking for:</strong> personal stories, career journeys, leadership stories, founder and business stories, community impact, workplace stories, reinvention, and stories of overcoming barriers — from women at any career stage, in any country.</p>
          <p><strong className="text-charcoal">Who can submit:</strong> anyone — about yourself, or about another woman (with her knowledge, where possible).</p>
          <p><strong className="text-charcoal">What happens next:</strong> our editorial team reviews every submission. We may follow up for more information. We can't guarantee acceptance or a specific response time.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">About you</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <input required placeholder="First name" value={form.firstName} onChange={(e) => setField('firstName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <input required placeholder="Last name" value={form.lastName} onChange={(e) => setField('lastName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <input required type="email" placeholder="Email address" value={form.email} onChange={(e) => setField('email', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <CountrySelect required value={form.countryCode} onChange={(countryCode) => setField('countryCode', countryCode)} placeholder="Your country" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <input placeholder="City (optional)" value={form.city} onChange={(e) => setField('city', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <input placeholder="Professional title (optional)" value={form.professionalTitle} onChange={(e) => setField('professionalTitle', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <input placeholder="Organization (optional)" value={form.organizationName} onChange={(e) => setField('organizationName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            <input type="url" placeholder="LinkedIn or website (optional)" value={form.linkedinUrl} onChange={(e) => setField('linkedinUrl', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>

          <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">About the story</p>
          <input required placeholder="Story title / working title" value={form.title} onChange={(e) => setField('title', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <textarea required placeholder="Short summary" rows={2} value={form.summary} onChange={(e) => setField('summary', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <textarea required placeholder="Your full story" rows={10} value={form.body} onChange={(e) => setField('body', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <textarea placeholder="Why does this story matter? (optional)" rows={2} value={form.whyItMatters} onChange={(e) => setField('whyItMatters', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
          <textarea placeholder="Key lessons or impact (optional)" rows={2} value={form.keyLessons} onChange={(e) => setField('keyLessons', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />

          <select value={form.storyType} onChange={(e) => setField('storyType', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
            <option value="">Story type (optional)</option>
            {STORY_TYPES.map((t) => (
              <option key={t} value={t}>{STORY_TYPE_LABELS[t]}</option>
            ))}
          </select>

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

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <select value={form.contentOrigin} onChange={(e) => setField('contentOrigin', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              <option value="">Is this previously published? (optional)</option>
              {CONTENT_ORIGINS.map((o) => (
                <option key={o} value={o}>{CONTENT_ORIGIN_LABELS[o]}</option>
              ))}
            </select>
            {form.contentOrigin === 'previously_published' && (
              <input type="url" placeholder="Link to the original publication" value={form.previousPublicationUrl} onChange={(e) => setField('previousPublicationUrl', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            )}
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">How was this story written?</label>
            <select value={form.aiInvolvement} onChange={(e) => setField('aiInvolvement', e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
              {AI_INVOLVEMENT_VALUES.map((v) => (
                <option key={v} value={v}>{AI_INVOLVEMENT_LABELS[v]}</option>
              ))}
            </select>
          </div>

          <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Subject</p>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input type="checkbox" checked={form.subjectIsSubmitter} onChange={(e) => setField('subjectIsSubmitter', e.target.checked)} className="mt-1" />
            This story is about me
          </label>
          {!form.subjectIsSubmitter && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <input required placeholder="Who is this story about?" value={form.subjectName} onChange={(e) => setField('subjectName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <input placeholder="Your relationship to her (optional)" value={form.subjectRelationship} onChange={(e) => setField('subjectRelationship', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
          )}

          <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Photo (optional)</p>
          <div className="space-y-3">
            {form.media.map((m, i) => (
              <div key={m.mediaId} className="flex items-start gap-3 border border-taupe-200 p-3">
                <img src={m.publicUrl} alt="" className="h-16 w-16 flex-shrink-0 object-cover" />
                <div className="flex-1 space-y-2">
                  <input placeholder="Caption (optional)" value={m.caption} onChange={(e) => updateMediaField(i, 'caption', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
                  <input placeholder="Photo credit (optional)" value={m.credit} onChange={(e) => updateMediaField(i, 'credit', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
                </div>
                <button type="button" onClick={() => removeMedia(i)} className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600">Remove</button>
              </div>
            ))}
            {form.media.length < MAX_IMAGES && (
              <label className="block cursor-pointer border border-dashed border-taupe-300 px-4 py-3 text-center text-sm text-charcoal-600 hover:border-burgundy-500">
                {uploadingMedia ? 'Uploading…' : 'Add a photo'}
                <input type="file" accept="image/*" onChange={handleAddImage} disabled={uploadingMedia} className="hidden" />
              </label>
            )}
            {form.media.length > 0 && (
              <label className="flex items-start gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.consentMediaRightsConfirmed} onChange={(e) => setField('consentMediaRightsConfirmed', e.target.checked)} className="mt-1" />
                I have permission to submit the image(s) above, including from anyone shown in them.
              </label>
            )}
          </div>

          <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Permissions</p>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input required type="checkbox" checked={form.consentReviewGiven} onChange={(e) => setField('consentReviewGiven', e.target.checked)} className="mt-1" />
            I give Women Shaping Futures permission to review this submission for possible publication.
          </label>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input required type="checkbox" checked={form.consentContactGiven} onChange={(e) => setField('consentContactGiven', e.target.checked)} className="mt-1" />
            I give Women Shaping Futures permission to contact me about this submission.
          </label>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input required type="checkbox" checked={form.consentAccuracyConfirmed} onChange={(e) => setField('consentAccuracyConfirmed', e.target.checked)} className="mt-1" />
            The information I've provided is accurate to the best of my knowledge.
          </label>
          <label className="flex items-start gap-2 text-sm text-charcoal-600">
            <input type="checkbox" checked={form.newsletterOptIn} onChange={(e) => setField('newsletterOptIn', e.target.checked)} className="mt-1" />
            Also subscribe me to the Women Shaping Futures newsletter
          </label>

          <button type="submit" disabled={submitting} className="btn-primary disabled:opacity-60">
            {submitting ? 'Submitting…' : 'Submit story'}
          </button>
          <p className="text-xs text-charcoal-600/70">
            Submitting a story doesn't guarantee publication. Our editorial team reviews every submission and may follow up if we need more information.
          </p>
        </form>
      </div>
    </div>
  )
}
