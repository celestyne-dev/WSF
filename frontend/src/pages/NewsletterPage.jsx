import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { ArrowRight } from 'lucide-react'
import { fetchNewsletterArchive } from '../api/newsletter'
import { fetchTopics } from '../api/taxonomies'
import { subscribe, resetNewsletterStatus } from '../features/newsletter/newsletterSlice'
import { withAcquisitionMetadata } from '../utils/analytics'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

export default function NewsletterPage() {
  const [archive, setArchive] = useState(null)
  const [topics, setTopics] = useState([])
  const [email, setEmail] = useState('')
  const [firstName, setFirstName] = useState('')
  const [topicSlugs, setTopicSlugs] = useState([])
  const dispatch = useDispatch()
  const status = useSelector((s) => s.newsletter.status)

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
    description: 'Subscribe to WSF Weekly for stories, jobs, and opportunities delivered every Thursday.',
    canonical: 'https://womenshapingfutures.org/newsletter',
  })

  function toggleTopic(slug) {
    setTopicSlugs((prev) => (prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email.includes('@')) {
      toast.error('Please enter a valid email address.')
      return
    }
    const result = await dispatch(
      subscribe(
        withAcquisitionMetadata({
          email,
          firstName: firstName || undefined,
          placement: 'newsletter-page',
          topicSlugs,
          consentTimestamp: new Date().toISOString(),
        }),
      ),
    )
    if (result.meta.requestStatus === 'fulfilled') {
      toast.success(result.payload.message)
      setEmail('')
      setFirstName('')
      setTopicSlugs([])
      dispatch(resetNewsletterStatus())
    } else {
      toast.error('Something went wrong. Please try again.')
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Newsletter" title="WSF Weekly" description="One email, every Thursday: the story worth your time, a woman worth knowing, and the jobs and opportunities worth applying for." />

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Subscribe</h2>
          <p className="mt-3 text-base text-charcoal-600">
            Join {archive ? new Intl.NumberFormat('en-US').format(archive.stats.subscriberCount) : '34,000'}+ readers. Free, always. Unsubscribe anytime.
          </p>

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

            {topics.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Topics you care about (optional)</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {topics.map((t) => (
                    <button
                      key={t.slug}
                      type="button"
                      onClick={() => toggleTopic(t.slug)}
                      className={`px-2.5 py-1 text-xs font-medium ${topicSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={status === 'loading'}
              className="inline-flex w-full items-center justify-center gap-2 bg-plum-600 px-6 py-3 text-sm font-semibold text-ivory transition-colors hover:bg-plum-700 disabled:opacity-60 sm:w-auto"
            >
              {status === 'loading' ? 'Subscribing…' : 'Subscribe'}
              <ArrowRight size={16} />
            </button>

            <p className="text-xs text-charcoal-600/70">
              By subscribing, you agree to receive the WSF Weekly newsletter by email. We never sell your
              information, and you can unsubscribe from any issue in one click.
            </p>
          </form>

          <h3 className="mt-10 font-serif text-lg font-semibold text-charcoal">What's inside every issue</h3>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-charcoal-600">
            <li>The featured story of the week</li>
            <li>A woman worth knowing</li>
            <li>Curated jobs and opportunities</li>
            <li>Career and business insights</li>
            <li>Upcoming events and resources</li>
          </ul>
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
