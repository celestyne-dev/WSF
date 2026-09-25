import { useEffect, useState } from 'react'
import { fetchRelatedArticles } from '../../api/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

/**
 * Manually curated — editors pick specific Articles and their order
 * (config.articleSlugs), unlike LatestStoriesModule's fully dynamic query.
 * fetchRelatedArticles already skips any slug that's missing/unpublished
 * (see api/articles.js), so a stale reference just quietly drops out of
 * the grid instead of rendering a broken card.
 */
export default function FeaturedStoriesModule({ module }) {
  const [items, setItems] = useState([])

  useEffect(() => {
    let active = true
    if (!module.articleSlugs?.length) {
      setItems([])
      return
    }
    fetchRelatedArticles(module.articleSlugs)
      .then((results) => active && setItems(results))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [module.articleSlugs])

  if (!items.length) return null

  return (
    <section className="py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow="Editors' picks" heading={module.heading} subheading={module.subheading} />
        <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      </div>
    </section>
  )
}
