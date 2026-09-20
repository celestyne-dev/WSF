import { getSeriesBySlug } from '../../mock/series'
import { getArticlesBySeries } from '../../mock/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function SeriesFeatureModule({ module }) {
  const seriesItem = getSeriesBySlug(module.seriesSlug)
  if (!seriesItem) return null
  const items = getArticlesBySeries(module.seriesSlug).slice(0, module.itemCount || 3)

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
