import { getArticlesByTopic } from '../../mock/articles'
import { getTopicBySlug } from '../../mock/topics'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function TopicCollectionModule({ module }) {
  const topic = getTopicBySlug(module.topicSlug)
  const items = getArticlesByTopic(module.topicSlug).slice(0, module.itemCount || 3)
  if (!topic || !items.length) return null

  return (
    <section className="py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow={topic.name} heading={module.heading} subheading={module.subheading} viewAllHref={`/topics/${topic.slug}`} />
        <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-3">
          {items.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      </div>
    </section>
  )
}
