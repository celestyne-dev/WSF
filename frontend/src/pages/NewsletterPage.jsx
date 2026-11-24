import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { ArrowRight } from 'lucide-react'
import { fetchNewsletterArchive } from '../api/newsletter'
import { fetchTopics } from '../api/taxonomies'
import { subscribe, resetNewsletterStatus } from '../features/newsletter/newsletterSlice'
import NewsletterConsent from '../components/newsletter/NewsletterConsent'
import { withAcquisitionMetadata } from '../utils/analytics'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import PageHeader from '../components/ui/PageHeader'

export default function NewsletterPage() {
  const [archive, setArchive] = useState(null)
  const [topics, setTopics] = useState([])
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [firstName, setFirstName] = useState('')
  const [topicSlugs, setTopicSlugs] = useState([])
  const dispatch = useDispatch()
  const status = useSelector((s) => s.newsletter.status)
  // CMS-editable value proposition (Studio > Settings > Engagement); the
  // defaults never promise a sending frequency nobody configured.
  const stored = useSelector((s) => s.site.settings?.newsletterPage)
  const page = {
    title: stored?.title || 'WSF Weekly',
    tagline: stored?.tagline || 'Your career briefing for women who want to move forward.',
    intro: stored?.intro || '',
    cadence: stored?.cadence || '',
    benefits: Array.isArray(stored?.benefits) ? stored.benefits : [],
  }

  useEffect(() => {
    let active = true
    Promise.all([fetchNewsletterArchive({ pageSize: 10 }), fetchTopics()])
      .then(([archiveData, topicList]) => {
        if (!active) return
        setArchive(archiveData)
        setTopics(topicList)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: 'WSF Weekly Newsletter | Women Shaping Futures',
    description: `${page.title}: ${page.tagline}`,
    canonical: 'https://womenshapingfutures.org/newsletter',
  })
  // Home > Newsletter — matches the server's own 2-level breadcrumb for this
  // list page (spa_shell.py's _LIST_PAGE_BREADCRUMB_LABELS).
  useBreadcrumbStructuredData([{ label: 'Newsletter' }], 'https://womenshapingfutures.org/newsletter')

  function toggleTopic(slug) {
    setTopicSlugs((prev) => (prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email.includes('@')) {
      toast.error('Please enter a valid email address.')
      return
    }
    if (!consent) {
      toast.error('Please tick the box to agree to receive the newsletter.')
      return
    }
    const result = await dispatch(
      subscribe(
        withAcquisitionMetadata({
          email,
          firstName: firstName || undefined,
          placement: 'newsletter-page',
          topicSlugs,
          consent: true,
        }),
      ),
    )
    if (result.meta.requestStatus === 'fulfilled' && result.payload.success) {
      toast.success(result.payload.message)
      setEmail('')
      setConsent(false)
      setFirstName('')
      setTopicSlugs([])
      dispatch(resetNewsletterStatus())
    } else {
      toast.error(result.payload?.message || 'Something went wrong. Please try again.')
      dispatch(resetNewsletterStatus())
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Newsletter" title={page.title} description={page.tagline} />
      {(page.intro || page.cadence) && (
        <div className="container-editorial pt-10">
          {page.intro && <p className="max-w-2xl text-base leading-relaxed text-charcoal-600">{page.intro}</p>}
          {page.cadence && <p className="mt-2 text-sm font-semibold text-charcoal">{page.cadence}</p>}
        </div>
      )}

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Subscribe</h2>
          {/* No reader count here: it would arrive after the page and push the
              form down, and a made-up fallback number is never shown. */}
          <p className="mt-3 text-base text-charcoal-600">Free. Unsubscribe anytime.</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-3" noValidate>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Your email address"
              className="w-full border border-taupe-300 bg-white px-4 py-3 text-sm text-charcoal placeholder:text-charcoal-600/60 focus:border-burgundy-500 focus:outline-none"
            />
            <input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="First name (optional)"
              className="w-full border border-taupe-300 bg-white px-4 py-3 text-sm text-charcoal placeholder:text-charcoal-600/60 focus:border-burgundy-500 focus:outline-none"
            />

            {/* Always present (collapsed), so the topic list arriving after the
                page never pushes the form down. */}
            <details className="group border border-taupe-200 bg-white px-4 py-3">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                Topics you care about (optional)
              </summary>
              <div className="mt-3 flex flex-wrap gap-2">
                {topics.map((t) => (
                  <button
                    key={t.slug}
                    type="button"
                    aria-pressed={topicSlugs.includes(t.slug)}
                    onClick={() => toggleTopic(t.slug)}
                    className={`px-2.5 py-1 text-xs font-medium ${topicSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                  >
                    {t.name}
                  </button>
                ))}
                {topics.length === 0 && <p className="text-xs text-charcoal-600">Loading topics…</p>}
              </div>
            </details>

            <button
              type="submit"
              disabled={status === 'loading'}
              className="inline-flex w-full items-center justify-center gap-2 bg-plum-600 px-6 py-3 text-sm font-semibold text-ivory transition-colors hover:bg-plum-700 disabled:opacity-60 sm:w-auto"
            >
              {status === 'loading' ? 'Subscribing…' : 'Subscribe'}
              <ArrowRight size={16} />
            </button>

            <NewsletterConsent id="newsletter-page-consent" checked={consent} onChange={setConsent} />
          </form>

          {page.benefits.length > 0 && (
            <>
              <h3 className="mt-10 font-serif text-lg font-semibold text-charcoal">What you get</h3>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-charcoal-600">
                {page.benefits.map((benefit) => (
                  <li key={benefit}>{benefit}</li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div>
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Recent issues</h2>
          {archive?.issues?.length ? (
            <div className="mt-5 divide-y divide-taupe-200">
              {archive.issues.map((issue) => (
                <div key={issue.id} className="py-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">
                    {issue.issueNumber ? `Issue #${issue.issueNumber} · ` : ''}
                    {issue.sentAt ? formatDate(issue.sentAt) : ''}
                  </p>
                  <Link to={`/newsletter/${issue.slug}`} className="mt-1 block font-serif text-xl font-semibold text-charcoal hover:text-burgundy-600">
                    {issue.subject}
                  </Link>
                  {issue.summary && <p className="mt-1 text-sm text-charcoal-600">{issue.summary}</p>}
                  {issue.featuredArticle?.slug && (
                    <Link to={`/${issue.featuredArticle.slug}`} className="mt-2 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
                      Read the featured story &rarr;
                    </Link>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-5 text-sm text-charcoal-600">No issues have been archived yet — check back soon.</p>
          )}
        </div>
      </div>
    </div>
  )
}
