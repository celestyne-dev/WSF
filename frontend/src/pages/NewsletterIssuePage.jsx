import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchNewsletterIssueBySlug } from '../api/newsletter'
import { resolveImage } from '../utils/media'
import { formatDate } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ShareBar from '../components/ui/ShareBar'
import NewsletterForm from '../components/ui/NewsletterForm'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

export default function NewsletterIssuePage() {
  const { slug } = useParams()
  const [issue, setIssue] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setIssue(undefined)
    setError(null)

    fetchNewsletterIssueBySlug(slug)
      .then((data) => {
        if (!active) return
        setIssue(data)
        if (data) trackEvent('newsletter_archive_view', { issueSlug: data.slug })
      })
      .catch(() => active && setError('Something went wrong loading this issue. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = issue ? `https://womenshapingfutures.org/newsletter/${issue.slug}` : ''

  useSeo(
    issue
      ? {
          title: `${issue.subject} | WSF Weekly Archive`,
          description: issue.preheader || issue.summary || issue.subject,
          canonical: canonicalUrl,
          image: issue.coverMedia?.mediaPath ? resolveImage(issue.coverMedia.mediaPath, { width: 1200, height: 630 }) : undefined,
        }
      : {},
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this issue" description={error} /></div>
  if (issue === undefined) return <PageLoader />
  if (issue === null) return <NotFoundPage />

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Newsletter', to: '/newsletter' }, { label: issue.subject }]} />
      </div>
      <div className="container-editorial max-w-reading py-10">
        {issue.coverMedia && (
          <MediaImage media={issue.coverMedia} variant="hero" width={1200} height={630} aspect={1.91 / 1} className="mb-8 w-full object-cover" />
        )}
        <span className="eyebrow">{issue.issueNumber ? `WSF Weekly #${issue.issueNumber}` : 'WSF Weekly'}</span>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{issue.subject}</h1>
        <p className="mt-2 text-sm text-charcoal-600">Sent {issue.sentAt ? formatDate(issue.sentAt) : ''}</p>

        <div className="mt-8">
          <ArticleContent blocks={issue.content} />
        </div>

        <div className="mt-10 border-t border-taupe-200 pt-6">
          <ShareBar title={issue.subject} url={canonicalUrl} trackEventName="newsletter_share_click" trackPayload={{ issueSlug: issue.slug }} />
        </div>
      </div>

      <section className="border-t border-taupe-200 bg-charcoal py-14 text-ivory">
        <div className="container-editorial flex flex-col items-center text-center">
          <p className="eyebrow !text-blush-200">WSF Weekly</p>
          <h2 className="mt-3 max-w-xl font-serif text-2xl font-semibold sm:text-3xl">Get the next issue in your inbox</h2>
          <div className="mt-6">
            <NewsletterForm variant="dark" source="newsletter_archive" />
          </div>
          <Link to="/newsletter" className="mt-4 text-sm font-semibold text-ivory/80 hover:text-ivory">
            Browse the full archive &rarr;
          </Link>
        </div>
      </section>
    </div>
  )
}
