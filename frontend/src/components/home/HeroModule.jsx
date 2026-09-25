import { useEffect, useState } from 'react'
import { fetchArticleBySlug, fetchRelatedArticles } from '../../api/articles'
import ArticleCard from '../cards/ArticleCard'
import MediaImage from '../ui/MediaImage'
import CtaLink from '../ui/CtaLink'

/**
 * Two content sources (see spec "Hero content source"):
 *  - a selected lead Article populates headline/image/excerpt automatically
 *    (module.leadArticleSlug) — `heading`/`ctaLabel`/`ctaUrl` on the module
 *    act as optional overrides on top of it, not a second source of truth.
 *  - with no lead article, the hero is fully editorial: `heading`,
 *    `subheading`, `media`, and up to two CTAs, all CMS-managed. This is
 *    the only place on the homepage that renders an <h1> — the article-
 *    driven path defers to ArticleCard's own heading, which intentionally
 *    stays an <h2> since that component is shared with non-hero contexts.
 */
export default function HeroModule({ module }) {
  const [lead, setLead] = useState(module.leadArticleSlug ? undefined : null)
  const [secondary, setSecondary] = useState([])

  useEffect(() => {
    if (!module.leadArticleSlug) {
      setLead(null)
      return
    }
    let active = true
    fetchArticleBySlug(module.leadArticleSlug)
      .then((data) => active && setLead(data))
      .catch(() => active && setLead(null))
    if (module.secondaryArticleSlugs?.length) {
      fetchRelatedArticles(module.secondaryArticleSlugs)
        .then((items) => active && setSecondary(items))
        .catch(() => {})
    }
    return () => {
      active = false
    }
  }, [module.leadArticleSlug, module.secondaryArticleSlugs])

  if (lead === undefined) return null // still resolving the lead article

  if (lead) {
    return (
      <section className="border-b border-taupe-200 bg-ivory py-10 sm:py-14">
        <div className="container-editorial grid grid-cols-1 gap-10 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ArticleCard article={module.heading ? { ...lead, title: module.heading } : lead} variant="lead" />
            {module.ctaLabel && module.ctaUrl && (
              <CtaLink to={module.ctaUrl} className="btn-outline mt-4 inline-flex">
                {module.ctaLabel}
              </CtaLink>
            )}
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

  if (!module.heading) return null // nothing manual configured either

  return (
    <section className="border-b border-taupe-200 bg-ivory py-14 sm:py-20">
      <div className="container-editorial grid grid-cols-1 items-center gap-10 lg:grid-cols-2">
        <div>
          <h1 className="font-serif text-4xl font-semibold leading-tight text-charcoal sm:text-5xl">
            {module.heading}
          </h1>
          {module.subheading && <p className="mt-4 max-w-xl text-lg text-charcoal-600">{module.subheading}</p>}
          <div className="mt-7 flex flex-wrap gap-3">
            {module.ctaLabel && module.ctaUrl && (
              <CtaLink to={module.ctaUrl} className="btn-primary">
                {module.ctaLabel}
              </CtaLink>
            )}
            {module.secondaryCtaLabel && module.secondaryCtaUrl && (
              <CtaLink to={module.secondaryCtaUrl} className="btn-outline">
                {module.secondaryCtaLabel}
              </CtaLink>
            )}
          </div>
        </div>
        {module.media && (
          <MediaImage
            media={module.media}
            variant="hero"
            alt={module.media.altText || module.heading}
            width={1200}
            height={800}
            aspect={3 / 2}
            priority
            className="aspect-[3/2] w-full object-cover"
          />
        )}
      </div>
    </section>
  )
}
