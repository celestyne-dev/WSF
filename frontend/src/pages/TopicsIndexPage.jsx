import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchTopics } from '../api/taxonomies'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

const CANONICAL = 'https://womenshapingfutures.org/topics'

export default function TopicsIndexPage() {
  const [topics, setTopics] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Stories by Topic | Women Shaping Futures',
    description: 'Explore Women Shaping Futures stories by topic — leadership, careers, entrepreneurship, money, technology, and more.',
    canonical: CANONICAL,
  })
  // Home > Topics — matches the server's own 2-level breadcrumb for this
  // list page (spa_shell.py's _LIST_PAGE_BREADCRUMB_LABELS["topics"]), so
  // this hook finds and reuses the server-rendered tag rather than
  // appending a duplicate, and removes it on navigating away.
  useBreadcrumbStructuredData([{ label: 'Topics' }], CANONICAL)

  useEffect(() => {
    let active = true
    fetchTopics()
      .then((data) => active && setTopics(data))
      .catch(() => active && setError('Something went wrong loading topics. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <PageHeader eyebrow="Stories" title="Browse by Topic" description="Every story we publish, organized around the themes that matter most to the women who read us." />
      <div className="container-editorial py-14">
        {error && <EmptyState title="Couldn't load topics" description={error} />}
        {!error && topics === null && <PageLoader />}
        {!error && topics !== null && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {topics.map((topic) => (
              <Link
                key={topic.id}
                to={`/topics/${topic.slug}`}
                className="group border border-taupe-200 bg-white p-6 transition-colors hover:border-burgundy-500/40"
              >
                <h2 className="font-serif text-xl font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">{topic.name}</h2>
                <p className="mt-2 text-sm text-charcoal-600">{topic.description}</p>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">{topic.articleCount} stories</p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
