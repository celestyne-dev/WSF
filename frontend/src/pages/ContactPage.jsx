import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { ArrowRight, Mail } from 'lucide-react'
import { fetchPublicPage } from '../api/pages'
import { submitContactInquiry } from '../api/contact'
import { CONTACT_INQUIRY_TYPES, CONTACT_INQUIRY_TYPE_LABELS } from '../constants/contact'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import InstitutionalPageHero from '../components/pages/InstitutionalPageHero'
import InstitutionalPageShell from '../components/pages/InstitutionalPageShell'
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
  // Home > (the real public CMS page display title, page.title) —
  // matches the server's own breadcrumb for this page (spa_shell.py's
  // _render_system_page_shell, same page.title) even though Contact's
  // own useSeo title above has no page.title fallback of its own —
  // the breadcrumb is a different, display-title semantic from the
  // meta title, so it never goes undefined when no custom SEO title
  // is configured.
  useBreadcrumbStructuredData(page ? [{ label: page?.title }] : null, 'https://womenshapingfutures.org/contact')

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
      <InstitutionalPageHero eyebrow="Contact" title={page.title} description={page.subtitle} />

      {page.content?.length > 0 && (
        <InstitutionalPageShell maxWidthClassName="mx-auto max-w-reading">
          <ArticleContent blocks={page.content} />
        </InstitutionalPageShell>
      )}

      <div className="border-t border-taupe-200 bg-cream/50">
        <div className="container-editorial py-14 sm:py-16 lg:py-20">
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-12 lg:gap-16">
            <div className="lg:col-span-5">
              <p className="eyebrow">Looking for something specific?</p>
              <h2 className="mt-2 font-serif text-2xl font-semibold text-charcoal sm:text-3xl">A dedicated route for common requests</h2>
              <p className="mt-3 text-sm leading-relaxed text-charcoal-600">
                These have their own process — you&rsquo;ll get a faster, more relevant response there than through the general form.
              </p>
              <div className="mt-8 divide-y divide-taupe-200 border-y border-taupe-200">
                {SPECIALIZED_ROUTES.map((r) => (
                  <Link
                    key={r.to}
                    to={r.to}
                    className="group flex items-start justify-between gap-4 py-5 transition-colors hover:bg-ivory/60"
                  >
                    <div>
                      <p className="font-serif text-lg font-medium text-charcoal group-hover:text-burgundy-600">{r.label}</p>
                      <p className="mt-1 text-sm text-charcoal-600">{r.description}</p>
                    </div>
                    <ArrowRight
                      size={18}
                      className="mt-1 shrink-0 text-charcoal-600/50 transition-transform group-hover:translate-x-0.5 group-hover:text-burgundy-600"
                      aria-hidden="true"
                    />
                  </Link>
                ))}
              </div>

              {contactEmail && (
                <div className="mt-8 border border-taupe-200 bg-ivory p-6">
                  <p className="eyebrow flex items-center gap-2">
                    <Mail size={14} aria-hidden="true" />
                    Prefer email?
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-charcoal-600">
                    Reach us directly at{' '}
                    <a href={`mailto:${contactEmail}`} className="font-medium text-burgundy-600 hover:underline">
                      {contactEmail}
                    </a>
                    .
                  </p>
                </div>
              )}
            </div>

            <div className="lg:col-span-7">
              <div className="border border-taupe-200 bg-ivory p-6 sm:p-10">
                <p className="eyebrow">General inquiry</p>
                <h2 className="mt-2 font-serif text-2xl font-semibold text-charcoal sm:text-3xl">Send us a message</h2>
                <p className="mt-3 text-sm leading-relaxed text-charcoal-600">
                  For everything else — feedback, technical issues, media requests, speaking inquiries, or anything not listed here.
                </p>

                {status === 'success' && result ? (
                  <div role="status" className="mt-8 border border-emerald-200 bg-emerald-50 p-6">
                    <p className="font-serif text-lg font-semibold text-charcoal">Message received</p>
                    <p className="mt-2 text-sm text-charcoal-600">{result.message}</p>
                    <button type="button" onClick={() => setStatus('idle')} className="mt-4 text-sm font-semibold text-burgundy-600 hover:underline">
                      Send another message
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-5" aria-busy={status === 'submitting'}>
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

                    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                      <div>
                        <label htmlFor="cf-firstName" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                          First name
                        </label>
                        <input
                          id="cf-firstName"
                          required
                          value={form.firstName}
                          onChange={(e) => setForm({ ...form, firstName: e.target.value })}
                          className="w-full border border-taupe-300 bg-ivory px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label htmlFor="cf-lastName" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                          Last name
                        </label>
                        <input
                          id="cf-lastName"
                          required
                          value={form.lastName}
                          onChange={(e) => setForm({ ...form, lastName: e.target.value })}
                          className="w-full border border-taupe-300 bg-ivory px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
                        />
                      </div>
                    </div>

                    <div>
                      <label htmlFor="cf-email" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                        Email address
                      </label>
                      <input
                        id="cf-email"
                        required
                        type="email"
                        value={form.email}
                        onChange={(e) => setForm({ ...form, email: e.target.value })}
                        className="w-full border border-taupe-300 bg-ivory px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label htmlFor="cf-inquiryType" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                        Inquiry type
                      </label>
                      <select
                        id="cf-inquiryType"
                        value={form.inquiryType}
                        onChange={(e) => setForm({ ...form, inquiryType: e.target.value })}
                        className="w-full border border-taupe-300 bg-ivory px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
                      >
                        {CONTACT_INQUIRY_TYPES.map((t) => (
                          <option key={t} value={t}>{CONTACT_INQUIRY_TYPE_LABELS[t]}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label htmlFor="cf-subject" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                        Subject
                      </label>
                      <input
                        id="cf-subject"
                        required
                        maxLength={200}
                        value={form.subject}
                        onChange={(e) => setForm({ ...form, subject: e.target.value })}
                        className="w-full border border-taupe-300 bg-ivory px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label htmlFor="cf-message" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                        Message
                      </label>
                      <textarea
                        id="cf-message"
                        required
                        rows={5}
                        minLength={10}
                        maxLength={5000}
                        value={form.message}
                        onChange={(e) => setForm({ ...form, message: e.target.value })}
                        className="w-full border border-taupe-300 bg-ivory px-4 py-3 text-sm text-charcoal focus:border-burgundy-500 focus:outline-none"
                      />
                    </div>

                    <label className="flex items-start gap-2 border-t border-taupe-200 pt-5 text-sm text-charcoal-600">
                      <input
                        required
                        type="checkbox"
                        checked={form.privacyAcknowledged}
                        onChange={(e) => setForm({ ...form, privacyAcknowledged: e.target.checked })}
                        className="mt-0.5"
                      />
                      I&rsquo;ve read the{' '}
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
        </div>
      </div>
    </div>
  )
}
