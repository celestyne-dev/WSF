import { useEffect, useState } from 'react'
import { fetchTopicBySlug, mapTopicDetail } from '../../api/taxonomies'
import { fetchArticles, mapArticle } from '../../api/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function TopicCollectionModule({ module }) {
  const initialTopic = module.initialData?.topic
  // `topic: null` is the server's 404 answer (nothing to show).
  const topicNotFound = Boolean(module.initialData) && module.initialData.topic === null
  const initialArticles = module.initialData?.articles
  const [topic, setTopic] = useState(() => (initialTopic ? mapTopicDetail(initialTopic) : topicNotFound ? null : undefined))
  const [items, setItems] = useState(() => (initialArticles ? initialArticles.map(mapArticle) : []))

  useEffect(() => {
    if (!module.topicSlug || topicNotFound || (initialTopic && initialArticles)) return
    let active = true
    fetchTopicBySlug(module.topicSlug)
      .then((data) => {
        if (!active) return
        setTopic(data)
        if (!data) return
        fetchArticles({ topic: module.topicSlug, pageSize: module.itemCount || 3 })
          .then((res) => active && setItems(res.items))
          .catch(() => {})
      })
      .catch(() => active && setTopic(null))
    return () => {
      active = false
    }
  }, [module.topicSlug, module.itemCount, initialTopic, initialArticles, topicNotFound])

  if (!module.topicSlug || !topic || !items.length) return null

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
