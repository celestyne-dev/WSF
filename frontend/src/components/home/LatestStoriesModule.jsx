import { getLatestArticles } from '../../mock/articles'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'

export default function LatestStoriesModule({ module }) {
  const items = getLatestArticles(module.itemCount || 8)
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
