import { useEffect, useState } from 'react'
import { fetchArticles } from '../../api/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function LatestStoriesModule({ module }) {
  const [items, setItems] = useState([])
  // 'loading' | 'error' | 'success' — only a confirmed successful fetch
  // that came back empty hides the section; a slow or failed fetch keeps
  // rendering the section exactly as before (no flash of "nothing here"
  // while still loading, and an error is never treated as empty).
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let active = true
    fetchArticles({ pageSize: module.itemCount || 8 })
      .then((res) => {
        if (!active) return
        setItems(res.items)
        setStatus('success')
      })
      .catch(() => active && setStatus('error'))
    return () => {
      active = false
    }
  }, [module.itemCount])

  if (status === 'success' && items.length === 0) return null

  return (
    <section className="py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow="Fresh this week" heading={module.heading} subheading={module.subheading} viewAllHref="/topics" viewAllLabel="All stories" />
        <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      </div>
    </section>
  )
}
