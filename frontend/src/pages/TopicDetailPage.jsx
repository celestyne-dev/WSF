import { useParams } from 'react-router-dom'
import { getTopicBySlug } from '../mock/topics'
import { getArticlesByTopic } from '../mock/articles'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import Breadcrumb from '../components/ui/Breadcrumb'
import ArticleCard from '../components/cards/ArticleCard'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

export default function TopicDetailPage() {
  const { slug } = useParams()
  const topic = getTopicBySlug(slug)
  if (!topic) return <NotFoundPage />

  const articles = getArticlesByTopic(slug)

  useSeo({
    title: `${topic.name} | Women Shaping Futures`,
    description: topic.description,
    canonical: `https://womenshapingfutures.org/topics/${topic.slug}`,
  })

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
