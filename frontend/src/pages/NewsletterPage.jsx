import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchNewsletterArchive } from '../api/site'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import NewsletterForm from '../components/ui/NewsletterForm'

export default function NewsletterPage() {
  const [archive, setArchive] = useState(null)

  useEffect(() => {
    let active = true
    fetchNewsletterArchive()
      .then((data) => active && setArchive(data))
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

  return (
    <div>
      <PageHeader eyebrow="Newsletter" title="WSF Weekly" description="One email, every Thursday: the story worth your time, a woman worth knowing, and the jobs and opportunities worth applying for." />

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Subscribe</h2>
          <p className="mt-3 text-base text-charcoal-600">
            Join {archive ? new Intl.NumberFormat('en-US').format(archive.stats.subscriberCount) : '34,000'}+ readers. Free, always. Unsubscribe anytime.
          </p>
          <div className="mt-6">
            <NewsletterForm source="newsletter-page" />
          </div>
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
          <div className="mt-5 divide-y divide-taupe-200">
            {archive?.issues.map((issue) => (
              <div key={issue.id} className="py-5">
                <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">
                  Issue #{issue.issueNumber} &middot; {formatDate(issue.sendDate)}
                </p>
                <h3 className="mt-1 font-serif text-xl font-semibold text-charcoal">{issue.subject}</h3>
                <p className="mt-1 text-sm text-charcoal-600">{issue.summary}</p>
                {issue.featuredArticleSlug && (
                  <Link to={`/${issue.featuredArticleSlug}`} className="mt-2 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
                    Read the featured story &rarr;
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
