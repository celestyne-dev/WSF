import { getArticleBySlug } from '../../mock/articles'
import ArticleCard from '../cards/ArticleCard'

export default function HeroModule({ module }) {
  const lead = getArticleBySlug(module.leadArticleSlug)
  const secondary = (module.secondaryArticleSlugs || []).map((s) => getArticleBySlug(s)).filter(Boolean)
  if (!lead) return null

  return (
    <section className="border-b border-taupe-200 bg-ivory py-10 sm:py-14">
      <div className="container-editorial grid grid-cols-1 gap-10 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ArticleCard article={lead} variant="lead" />
        </div>
        <div className="flex flex-col gap-6 lg:border-l lg:border-taupe-200 lg:pl-10">
          {secondary.map((article) => (
            <ArticleCard key={article.id} article={article} variant="horizontal" />
          ))}
        </div>
      </div>
    </section>
  )
}
