import { useEffect, useState } from 'react'
import { fetchSeriesBySlug } from '../../api/taxonomies'
import { fetchArticles } from '../../api/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function SeriesFeatureModule({ module }) {
  const [seriesItem, setSeriesItem] = useState(undefined)
  const [items, setItems] = useState([])

  useEffect(() => {
    let active = true
    fetchSeriesBySlug(module.seriesSlug)
      .then((data) => {
        if (!active) return
        setSeriesItem(data)
        if (!data) return
        fetchArticles({ series: module.seriesSlug, pageSize: module.itemCount || 3 })
          .then((res) => active && setItems(res.items))
          .catch(() => {})
      })
      .catch(() => active && setSeriesItem(null))
    return () => {
      active = false
    }
  }, [module.seriesSlug, module.itemCount])

  if (!seriesItem) return null

  return (
    <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading
          eyebrow="Series"
          heading={module.heading}
          subheading={seriesItem.description}
          viewAllHref={`/series/${seriesItem.slug}`}
          viewAllLabel="View series"
        />
        <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-3">
          {items.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      </div>
    </section>
  )
}
