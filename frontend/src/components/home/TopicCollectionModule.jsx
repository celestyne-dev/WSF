import { useEffect, useState } from 'react'
import { fetchTopicBySlug } from '../../api/taxonomies'
import { fetchArticles } from '../../api/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function TopicCollectionModule({ module }) {
  const [topic, setTopic] = useState(undefined)
  const [items, setItems] = useState([])

  useEffect(() => {
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
  }, [module.topicSlug, module.itemCount])

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
