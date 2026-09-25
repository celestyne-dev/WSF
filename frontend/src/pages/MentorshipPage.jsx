import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { fetchPublicPrograms, submitMentorshipApplication } from '../api/mentorship'
import { fetchCountries } from '../api/geography'
import { fetchTopics } from '../api/taxonomies'
import { withAcquisitionMetadata, trackEvent } from '../utils/analytics'
import { CAREER_STAGES, MEETING_FREQUENCIES, MENTORSHIP_FORMATS } from '../constants/mentorship'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import ArticleContent from '../components/article/ArticleContent'

function blankForm(programId, role) {
  return {
    programId, role,
    firstName: '', lastName: '', email: '', countryCode: '',
    professionalTitle: '', organizationName: '', industry: '', yearsExperience: '',
    linkedinUrl: '', websiteUrl: '',
    backgroundText: '', goalsText: '', supportOfferedText: '',
    careerStage: '', careerStagesSupported: [],
    timezone: '', meetingFrequency: '', mentorshipFormat: '', availabilityNote: '',
    topicSlugs: [],
    consentGiven: false, subscribeNewsletter: false,
  }
}

export default function MentorshipPage() {
  const [programs, setPrograms] = useState(undefined)
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [form, setForm] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let active = true
    fetchPublicPrograms()
      .then((list) => {
        if (!active) return
        setPrograms(list)
        trackEvent('mentorship_page_view')
      })
      .catch(() => active && setPrograms([]))
    fetchCountries().then((list) => active && setCountries([...list].sort((a, b) => a.name.localeCompare(b.name)))).catch(() => {})
    fetchTopics().then((list) => active && setTopics(list)).catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: 'Mentorship | Women Shaping Futures',
    description: 'WSF Mentorship — find a mentor, become a mentor, and join a structured mentorship program.',
    canonical: 'https://womenshapingfutures.org/mentorship',
  })

  function startApplication(program, role) {
    setForm(blankForm(program.id, role))
    trackEvent(role === 'mentor' ? 'mentor_application_start' : 'mentee_application_start', { programId: program.id })
    requestAnimationFrame(() => {
      document.getElementById('mentorship-apply')?.scrollIntoView({ behavior: 'smooth' })
    })
  }

  function handleFieldChange(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  function toggleCareerStageSupported(stage) {
    setForm((prev) => ({
      ...prev,
      careerStagesSupported: prev.careerStagesSupported.includes(stage)
        ? prev.careerStagesSupported.filter((s) => s !== stage)
        : [...prev.careerStagesSupported, stage],
    }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentGiven) {
      toast.error('Please confirm we may use your submitted information to process your application.')
      return
    }
    setSubmitting(true)
    const result = await submitMentorshipApplication(withAcquisitionMetadata(form))
    setSubmitting(false)
    if (result.success) {
      trackEvent(form.role === 'mentor' ? 'mentor_application_submit' : 'mentee_application_submit', { programId: form.programId })
      toast.success(result.message)
      setForm(null)
    } else {
      toast.error(result.message)
    }
  }

  if (programs === undefined) return <PageLoader />

  const activeProgram = form ? programs.find((p) => p.id === form.programId) : null
  const isMentor = form?.role === 'mentor'

  return (
    <div>
      <PageHeader
        eyebrow="Mentorship"
        title="WSF Mentorship"
        description="Structured mentorship connecting ambitious women with experienced leaders across industries, career stages, and countries."
      />

      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-10 border-b border-taupe-200 pb-14 sm:grid-cols-2">
          <div>
            <h2 className="font-serif text-2xl font-semibold text-charcoal">Find a mentor</h2>
            <p className="mt-3 text-sm text-charcoal-600">
              Get matched with an experienced leader who can support your goals — from career transitions to leadership growth.
            </p>
          </div>
          <div>
            <h2 className="font-serif text-2xl font-semibold text-charcoal">Become a mentor</h2>
            <p className="mt-3 text-sm text-charcoal-600">
              Share what you've learned. Mentors set their own capacity and the career stages they're comfortable supporting.
            </p>
          </div>
        </div>

        <div className="py-14">
          <h2 className="font-serif text-3xl font-semibold text-charcoal">Current programs</h2>
          {programs.length === 0 ? (
            <p className="mt-4 text-sm text-charcoal-600">No mentorship programs are open right now — check back soon.</p>
          ) : (
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2">
              {programs.map((program) => (
                <div key={program.id} className="border border-taupe-200 bg-white p-6">
                  <h3 className="font-serif text-xl font-semibold text-charcoal">{program.name}</h3>
                  {program.shortDescription && <p className="mt-2 text-sm text-charcoal-600">{program.shortDescription}</p>}
                  {program.fullDescription?.length > 0 && (
                    <div className="mt-3 text-sm text-charcoal-600">
                      <ArticleContent blocks={program.fullDescription} />
                    </div>
                  )}
                  {program.eligibilitySummary && <p className="mt-3 text-xs text-charcoal-600/70">{program.eligibilitySummary}</p>}
                  {program.topics?.length > 0 && (
                    <p className="mt-3 text-xs uppercase tracking-wide text-burgundy-600">{program.topics.join(' · ')}</p>
                  )}
                  <p className="mt-3 text-xs text-charcoal-600/60">
                    {program.applicationOpenNow
                      ? `Applications open${program.applicationClosesAt ? ` through ${formatDate(program.applicationClosesAt)}` : ''}.`
                      : 'Applications are currently closed for this program.'}
                  </p>
                  {program.applicationOpenNow && (
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button type="button" onClick={() => startApplication(program, 'mentee')} className="btn-primary !px-4 !py-2 text-xs">
                        Apply as a Mentee
                      </button>
                      <button type="button" onClick={() => startApplication(program, 'mentor')} className="btn-secondary !px-4 !py-2 text-xs">
                        Apply as a Mentor
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {form && activeProgram && (
          <div id="mentorship-apply" className="border-t border-taupe-200 py-14">
            <h2 className="font-serif text-2xl font-semibold text-charcoal">
              Apply as a {isMentor ? 'Mentor' : 'Mentee'} — {activeProgram.name}
            </h2>
            <form onSubmit={handleSubmit} className="mx-auto mt-6 max-w-2xl space-y-4" noValidate>
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Contact</p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <label className="sr-only" htmlFor="mf-firstName">First name</label>
                <input id="mf-firstName" required placeholder="First name" value={form.firstName} onChange={(e) => handleFieldChange('firstName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                <label className="sr-only" htmlFor="mf-lastName">Last name</label>
                <input id="mf-lastName" required placeholder="Last name" value={form.lastName} onChange={(e) => handleFieldChange('lastName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              </div>
              <label className="sr-only" htmlFor="mf-email">Email</label>
              <input id="mf-email" required type="email" placeholder="Email address" value={form.email} onChange={(e) => handleFieldChange('email', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <label className="sr-only" htmlFor="mf-country">Country</label>
              <select id="mf-country" required value={form.countryCode} onChange={(e) => handleFieldChange('countryCode', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
                <option value="">Select your country…</option>
                {countries.map((c) => (
                  <option key={c.code} value={c.code}>{c.name}</option>
                ))}
              </select>

              <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Professional background</p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <input placeholder="Current role / title (optional)" value={form.professionalTitle} onChange={(e) => handleFieldChange('professionalTitle', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                <input placeholder="Organization (optional)" value={form.organizationName} onChange={(e) => handleFieldChange('organizationName', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                <input placeholder="Industry / field (optional)" value={form.industry} onChange={(e) => handleFieldChange('industry', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                {isMentor ? (
                  <input type="number" min="0" placeholder="Years of experience (optional)" value={form.yearsExperience} onChange={(e) => handleFieldChange('yearsExperience', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                ) : (
                  <select value={form.careerStage} onChange={(e) => handleFieldChange('careerStage', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
                    <option value="">Career stage (optional)</option>
                    {CAREER_STAGES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                )}
              </div>
              <input type="url" placeholder="LinkedIn or website (optional)" value={form.linkedinUrl} onChange={(e) => handleFieldChange('linkedinUrl', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />

              <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">{isMentor ? 'Expertise' : 'Goals'}</p>
              <textarea placeholder="Your professional background (optional)" rows={2} value={form.backgroundText} onChange={(e) => handleFieldChange('backgroundText', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              <textarea
                placeholder={isMentor ? 'Why do you want to mentor? (optional)' : 'What are your mentorship goals? (optional)'}
                rows={2} value={form.goalsText} onChange={(e) => handleFieldChange('goalsText', e.target.value)}
                className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
              />
              {isMentor && (
                <textarea placeholder="What can you support mentees with? (optional)" rows={2} value={form.supportOfferedText} onChange={(e) => handleFieldChange('supportOfferedText', e.target.value)} className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
              )}

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

              {isMentor && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Career stages you're comfortable mentoring (optional)</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {CAREER_STAGES.map((s) => (
                      <button key={s} type="button" onClick={() => toggleCareerStageSupported(s)} className={`px-2.5 py-1 text-xs font-medium ${form.careerStagesSupported.includes(s) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Availability</p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <input placeholder="Timezone (optional)" value={form.timezone} onChange={(e) => handleFieldChange('timezone', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none" />
                <select value={form.meetingFrequency} onChange={(e) => handleFieldChange('meetingFrequency', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
                  <option value="">Meeting frequency (optional)</option>
                  {MEETING_FREQUENCIES.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
                <select value={form.mentorshipFormat} onChange={(e) => handleFieldChange('mentorshipFormat', e.target.value)} className="border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none">
                  <option value="">Format (optional)</option>
                  {MENTORSHIP_FORMATS.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>

              <label className="flex items-start gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.subscribeNewsletter} onChange={(e) => handleFieldChange('subscribeNewsletter', e.target.checked)} className="mt-0.5" />
                Also subscribe me to the Women Shaping Futures newsletter
              </label>
              <label className="flex items-start gap-2 text-sm text-charcoal-600">
                <input required type="checkbox" checked={form.consentGiven} onChange={(e) => handleFieldChange('consentGiven', e.target.checked)} className="mt-0.5" />
                I confirm the information above may be used by Women Shaping Futures to process this application.
              </label>

              <div className="flex items-center gap-3">
                <button type="submit" disabled={submitting} className="btn-primary disabled:opacity-60">
                  {submitting ? 'Submitting…' : `Submit ${isMentor ? 'mentor' : 'mentee'} application`}
                </button>
                <button type="button" onClick={() => setForm(null)} className="text-xs font-semibold text-charcoal-600/70 hover:text-charcoal">
                  Cancel
                </button>
              </div>
              <p className="text-xs text-charcoal-600/70">
                We can't guarantee acceptance or a specific response time, but our team reviews every application.
              </p>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
