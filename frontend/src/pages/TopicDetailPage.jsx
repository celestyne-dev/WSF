import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchTopicBySlug } from '../api/taxonomies'
import { fetchArticles } from '../api/articles'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import { resolveImage } from '../utils/media'
import PageHeader from '../components/ui/PageHeader'
import Breadcrumb from '../components/ui/Breadcrumb'
import ArticleCard from '../components/cards/ArticleCard'
import ArticleContent from '../components/article/ArticleContent'
import SourceReferences from '../components/article/SourceReferences'
import ProfilePreviewList from '../components/article/ProfilePreviewList'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import NotFoundPage from './NotFoundPage'

export default function TopicDetailPage() {
  const { slug } = useParams()
  const [topic, setTopic] = useState(undefined)
  const [articles, setArticles] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setTopic(undefined)
    setError(null)

    fetchTopicBySlug(slug)
      .then((data) => {
        if (!active) return
        setTopic(data)
        if (!data) return
        fetchArticles({ topic: slug })
          .then((res) => active && setArticles(res.items))
          .catch(() => {})
      })
      .catch(() => active && setError('Something went wrong loading this topic. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  useSeo(
    topic
      ? {
          title: topic.seo?.title || `${topic.name} | Women Shaping Futures`,
          description: topic.seo?.description || topic.description,
          canonical: topic.seo?.canonical || `https://womenshapingfutures.org/topics/${topic.slug}`,
          robots: topic.seo?.robots,
          image: topic.heroMedia ? resolveImage(topic.heroMedia, { width: 1200, height: 630 }) : undefined,
        }
      : {},
  )

  useBreadcrumbStructuredData(
    topic ? [{ label: 'Topics', to: '/topics' }, { label: topic.name }] : null,
    topic ? topic.seo?.canonical || `https://womenshapingfutures.org/topics/${topic.slug}` : null,
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this topic" description={error} /></div>
  if (topic === undefined) return <PageLoader />
  if (topic === null) return <NotFoundPage />

  // GEO Phase 4C — the curated "Start here" story is shown in its own block,
  // so it's dropped from this first page of latest stories (presentation
  // only; the grid has no pagination, so nothing else shifts).
  const featured = topic.featuredArticle
  const latest = featured ? articles.filter((a) => a.slug !== featured.slug) : articles
  const hasDepth = topic.content?.length > 0 || !!featured || topic.contributors?.length > 0

  return (
    <div>
      <PageHeader eyebrow="Topic" title={topic.name} description={topic.description}>
        <div className="mt-5">
          <Breadcrumb items={[{ label: 'Topics', to: '/topics' }, { label: topic.name }]} />
        </div>
      </PageHeader>
      <div className="container-editorial py-14">
        {topic.content?.length > 0 && (
          <div className="max-w-reading">
            <ArticleContent blocks={topic.content} />
          </div>
        )}

        {featured && (
          <section aria-labelledby="topic-start-here" className="mt-12 max-w-reading">
            <h2 id="topic-start-here" className="font-serif text-2xl font-semibold text-charcoal">
              Start here
            </h2>
            <div className="mt-5">
              <ArticleCard article={featured} variant="horizontal" />
            </div>
          </section>
        )}

        <ProfilePreviewList id="topic-contributors" heading="Contributors covering this topic" items={topic.contributors} basePath="/authors" metaKey="role" />

        <div className={hasDepth ? 'mt-14' : ''}>
          {hasDepth && <h2 className="mb-6 font-serif text-2xl font-semibold text-charcoal">Latest stories</h2>}
          {latest.length ? (
            <div className="grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
              {latest.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          ) : featured ? null : (
            <EmptyState title="No stories yet" description="We haven't published a story on this topic yet — check back soon." />
          )}
        </div>

        {topic.sources?.length > 0 && (
          <div className="max-w-reading">
            <SourceReferences sources={topic.sources} id="topic-sources" />
          </div>
        )}
      </div>
    </div>
  )
}
