import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchTopicBySlug } from '../api/taxonomies'
import { fetchArticles } from '../api/articles'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import Breadcrumb from '../components/ui/Breadcrumb'
import ArticleCard from '../components/cards/ArticleCard'
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
          title: `${topic.name} | Women Shaping Futures`,
          description: topic.description,
          canonical: `https://womenshapingfutures.org/topics/${topic.slug}`,
        }
      : {},
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this topic" description={error} /></div>
  if (topic === undefined) return <PageLoader />
  if (topic === null) return <NotFoundPage />

  return (
    <div>
      <PageHeader eyebrow="Topic" title={topic.name} description={topic.description}>
        <div className="mt-5">
          <Breadcrumb items={[{ label: 'Topics', to: '/topics' }, { label: topic.name }]} />
        </div>
      </PageHeader>
      <div className="container-editorial py-14">
        {articles.length ? (
          <div className="grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {articles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        ) : (
          <EmptyState title="No stories yet" description="We haven't published a story on this topic yet — check back soon." />
        )}
      </div>
    </div>
  )
}
