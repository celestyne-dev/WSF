import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { fetchPublicPage } from '../api/pages'
import { submitContactInquiry } from '../api/contact'
import { CONTACT_INQUIRY_TYPES, CONTACT_INQUIRY_TYPE_LABELS } from '../constants/contact'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

const SPECIALIZED_ROUTES = [
  { label: 'Partnership or sponsorship inquiry', description: 'Sponsored content, events, or brand collaborations.', to: '/partnerships' },
  { label: 'Advertising inquiry', description: 'Media kit, rates, and ad placements.', to: '/advertise' },
  { label: 'Share your story', description: 'Submit a personal or career story for editorial review.', to: '/submit' },
  { label: 'Nominate someone', description: 'Nominate a woman for recognition.', to: '/nominate' },
  { label: 'Mentorship', description: 'Apply as a mentor or mentee.', to: '/mentorship' },
]

function blankForm() {
  return { firstName: '', lastName: '', email: '', inquiryType: 'general', subject: '', message: '', privacyAcknowledged: false, hpWebsite: '' }
}

export default function ContactPage() {
  const [page, setPage] = useState(undefined)
  const [form, setForm] = useState(blankForm())
  const [status, setStatus] = useState('idle') // idle | submitting | success | error
  const [result, setResult] = useState(null)
  const startedAtRef = useRef(null)
  const contactEmail = useSelector((s) => s.site.settings?.contact?.email)

  useEffect(() => {
    startedAtRef.current = Date.now()
  }, [])

  useEffect(() => {
    let active = true
    fetchPublicPage('contact')
      .then((res) => active && setPage(res))
      .catch(() => active && setPage(null))
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: page?.seo?.title,
    description: page?.seo?.description,
    canonical: 'https://womenshapingfutures.org/contact',
  })

  async function handleSubmit(e) {
    e.preventDefault()
    if (status === 'submitting') return
    if (!form.privacyAcknowledged) {
      toast.error('Please acknowledge the privacy notice before submitting.')
      return
    }
    setStatus('submitting')
    const res = await submitContactInquiry(form, startedAtRef.current)
    if (res.success) {
      setStatus('success')
      setResult(res)
      setForm(blankForm())
    } else {
      setStatus('error')
      toast.error(res.message)
    }
  }

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  return (
    <div>
      <PageHeader eyebrow="Contact" title={page.title} description={page.subtitle} />
      <div className="container-editorial max-w-reading py-14">
        <ArticleContent blocks={page.content} />

        <div className="mt-14 border-t border-taupe-200 pt-14">
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Looking for something specific?</h2>
          <p className="mt-2 text-sm text-charcoal-600">
            These have their own dedicated process — you'll get a faster, more relevant response there than through the general form below.
          </p>
          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {SPECIALIZED_ROUTES.map((r) => (
              <Link
                key={r.to}
                to={r.to}
                className="border border-taupe-200 bg-white p-4 text-sm transition hover:border-burgundy-400"
              >
                <p className="font-semibold text-charcoal">{r.label}</p>
                <p className="mt-1 text-charcoal-600">{r.description}</p>
              </Link>
            ))}
          </div>
        </div>

        <div className="mt-14 border-t border-taupe-200 pt-14">
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Send a general inquiry</h2>
          <p className="mt-2 text-sm text-charcoal-600">
            For everything else — feedback, technical issues, media requests, speaking inquiries, or anything not listed above.
            {contactEmail && (
              <>
                {' '}
                You can also reach us directly at{' '}
                <a href={`mailto:${contactEmail}`} className="font-medium text-burgundy-600 hover:underline">
                  {contactEmail}
                </a>
                .
              </>
            )}
          </p>

          {status === 'success' && result ? (
            <div role="status" className="mt-6 border border-emerald-200 bg-emerald-50 p-6">
              <p className="font-serif text-lg font-semibold text-charcoal">Message received</p>
              <p className="mt-2 text-sm text-charcoal-600">{result.message}</p>
              <button type="button" onClick={() => setStatus('idle')} className="mt-4 text-sm font-semibold text-burgundy-600 hover:underline">
                Send another message
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4" aria-busy={status === 'submitting'}>
              {/* Honeypot — hidden from sighted users and screen readers; a
                  filled value means a bot. Named unlike any real field so
                  autofill doesn't touch it. */}
              <div aria-hidden="true" className="absolute -left-[9999px] top-auto h-0 w-0 overflow-hidden">
                <label htmlFor="cf-hp">Leave this field empty</label>
                <input
                  id="cf-hp"
                  type="text"
                  tabIndex={-1}
                  autoComplete="off"
                  value={form.hpWebsite}
                  onChange={(e) => setForm({ ...form, hpWebsite: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="cf-firstName" className="sr-only">First name</label>
                  <input
                    id="cf-firstName"
                    required
                    placeholder="First name"
                    value={form.firstName}
                    onChange={(e) => setForm({ ...form, firstName: e.target.value })}
                    className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label htmlFor="cf-lastName" className="sr-only">Last name</label>
                  <input
                    id="cf-lastName"
                    required
                    placeholder="Last name"
                    value={form.lastName}
                    onChange={(e) => setForm({ ...form, lastName: e.target.value })}
                    className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="cf-email" className="sr-only">Email address</label>
                <input
                  id="cf-email"
                  required
                  type="email"
                  placeholder="Email address"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="cf-inquiryType" className="sr-only">Inquiry type</label>
                <select
                  id="cf-inquiryType"
                  value={form.inquiryType}
                  onChange={(e) => setForm({ ...form, inquiryType: e.target.value })}
                  className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                >
                  {CONTACT_INQUIRY_TYPES.map((t) => (
                    <option key={t} value={t}>{CONTACT_INQUIRY_TYPE_LABELS[t]}</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="cf-subject" className="sr-only">Subject</label>
                <input
                  id="cf-subject"
                  required
                  placeholder="Subject"
                  maxLength={200}
                  value={form.subject}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })}
                  className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="cf-message" className="sr-only">Message</label>
                <textarea
                  id="cf-message"
                  required
                  rows={5}
                  placeholder="Your message"
                  minLength={10}
                  maxLength={5000}
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  className="w-full border border-taupe-300 px-4 py-3 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </div>

              <label className="flex items-start gap-2 text-sm text-charcoal-600">
                <input
                  required
                  type="checkbox"
                  checked={form.privacyAcknowledged}
                  onChange={(e) => setForm({ ...form, privacyAcknowledged: e.target.checked })}
                  className="mt-0.5"
                />
                I've read the{' '}
                <Link to="/privacy" className="font-medium text-burgundy-600 hover:underline">
                  Privacy Policy
                </Link>{' '}
                and agree to my information being used to respond to this inquiry.
              </label>

              <button type="submit" disabled={status === 'submitting'} className="btn-primary w-full disabled:opacity-60">
                {status === 'submitting' ? 'Sending…' : 'Send message'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
