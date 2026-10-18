import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
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
 *
 * WSF SEO Phase 2D: on a hard load of "/", the server has often already
 * resolved this exact lead Article (see store/index.js's preloadedState,
 * built from spa_shell.py's homepage bootstrap) — `state.site.leadArticle`
 * is it, when present. Using it directly here skips what would otherwise
 * be a second, serial fetch (homepage modules, THEN this Article) after
 * the homepage's own first fetch already resolved it server-side. A
 * plain client-side SPA navigation that never went through that bootstrap
 * (or a `module.leadArticleSlug` that doesn't match it) falls back to the
 * exact fetch this component always made.
 */
export default function HeroModule({ module }) {
  const bootstrapLeadArticle = useSelector((s) => s.site.leadArticle)
  const matchesBootstrap = Boolean(bootstrapLeadArticle) && bootstrapLeadArticle.slug === module.leadArticleSlug
  const [lead, setLead] = useState(() => {
    if (matchesBootstrap) return bootstrapLeadArticle
    return module.leadArticleSlug ? undefined : null
  })
  const [secondary, setSecondary] = useState([])

  useEffect(() => {
    let active = true
    if (!module.leadArticleSlug) {
      setLead(null)
    } else if (!matchesBootstrap) {
      fetchArticleBySlug(module.leadArticleSlug)
        .then((data) => active && setLead(data))
        .catch(() => active && setLead(null))
    }
    // else: matchesBootstrap — `lead` is already the resolved Article
    // from the lazy initializer above; no fetch needed.

    if (module.secondaryArticleSlugs?.length) {
      fetchRelatedArticles(module.secondaryArticleSlugs)
        .then((items) => active && setSecondary(items))
        .catch(() => {})
    }
    return () => {
      active = false
    }
  }, [module.leadArticleSlug, module.secondaryArticleSlugs, matchesBootstrap])

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
            sizes="(min-width: 1024px) 50vw, 100vw"
            priority
            className="aspect-[3/2] w-full object-cover"
          />
        )}
      </div>
    </section>
  )
}
