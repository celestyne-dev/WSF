import { useEffect, useState } from 'react'
import { fetchSeriesBySlug, mapSeriesDetail } from '../../api/taxonomies'
import { fetchArticles, mapArticle } from '../../api/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function SeriesFeatureModule({ module }) {
  // Hard load of "/": the server already fetched both (module.initialData).
  const initialSeries = module.initialData?.series
  // `series: null` is the server's 404 answer (nothing to show).
  const seriesNotFound = Boolean(module.initialData) && module.initialData.series === null
  const initialArticles = module.initialData?.articles
  const [seriesItem, setSeriesItem] = useState(() => (initialSeries ? mapSeriesDetail(initialSeries) : seriesNotFound ? null : undefined))
  const [items, setItems] = useState(() => (initialArticles ? initialArticles.map(mapArticle) : []))
  // 'loading' | 'error' | 'success' for the nested articles fetch only —
  // the Series entity itself is already guarded below (!seriesItem). This
  // separately guards against a resolved Series with zero eligible
  // stories rendering an empty ArticleCard grid, without hiding the
  // module while that second fetch is still in flight or has failed.
  const [storiesStatus, setStoriesStatus] = useState(initialArticles ? 'success' : 'loading')

  useEffect(() => {
    if (!module.seriesSlug || seriesNotFound || (initialSeries && initialArticles)) return
    let active = true
    fetchSeriesBySlug(module.seriesSlug)
      .then((data) => {
        if (!active) return
        setSeriesItem(data)
        if (!data) return
        fetchArticles({ series: module.seriesSlug, pageSize: module.itemCount || 3 })
          .then((res) => {
            if (!active) return
            setItems(res.items)
            setStoriesStatus('success')
          })
          .catch(() => active && setStoriesStatus('error'))
      })
      .catch(() => active && setSeriesItem(null))
    return () => {
      active = false
    }
  }, [module.seriesSlug, module.itemCount, initialSeries, initialArticles, seriesNotFound])

  if (!module.seriesSlug || !seriesItem) return null
  if (storiesStatus === 'success' && items.length === 0) return null

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
