import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import { resolveAltText } from '../../utils/media'
import { formatShortDate } from '../../utils/format'
import { resolveReadingTime } from '../../utils/readingTime'

/**
 * variant: 'lead' | 'secondary' | 'horizontal' | 'compact' | 'grid'
 * Article URLs are flat: /{slug} — never /articles/{slug}.
 *
 * `article` must be a normalized object from api/articles.js — its
 * `author`/`topic` fields are already resolved there (mapArticle for real
 * mode, enrichMockArticle for mock mode). This component never looks
 * authors/topics up itself.
 */
export default function ArticleCard({ article, variant = 'grid' }) {
  if (!article) return null
  const { author, topic } = article
  const href = `/${article.slug}`

  if (variant === 'lead') {
    return (
      <article className="group relative">
        <Link to={href} className="block overflow-hidden">
          <MediaImage
            media={article.heroMedia}
            variant="large"
            mediaPath={article.heroImage}
            alt={resolveAltText(article.heroMedia, article.title)}
            width={1400}
            height={933}
            // This variant is only ever used once, for the homepage's
            // selected lead article (see HeroModule) — genuinely the
            // page's LCP candidate, so it keeps `priority`. Roughly 2/3
            // of the content column on desktop (lg:col-span-2 of 3),
            // full width below that.
            sizes="(min-width: 1024px) 66vw, 100vw"
            priority
            className="aspect-[3/2] w-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.02]"
          />
        </Link>
        <div className="mt-5">
          {topic && (
            <Link to={`/topics/${topic.slug}`} className="eyebrow">
              {topic.name}
            </Link>
          )}
          <h2 className="mt-2 font-serif text-3xl font-semibold leading-tight text-charcoal sm:text-4xl lg:text-[2.75rem]">
            <Link to={href} className="transition-colors hover:text-burgundy-600">
              {article.title}
            </Link>
          </h2>
          <p className="mt-3 max-w-xl text-base text-charcoal-600">{article.excerpt}</p>
          <div className="mt-4 flex items-center gap-2 text-sm text-charcoal-600">
            {author && <span className="font-medium text-charcoal">{author.name}</span>}
            <span aria-hidden="true">&middot;</span>
            <span>{formatShortDate(article.publishDate)}</span>
            <span aria-hidden="true">&middot;</span>
            <span>{resolveReadingTime(article)} min read</span>
          </div>
        </div>
      </article>
    )
  }

  if (variant === 'horizontal') {
    return (
      <article className="group flex gap-4 sm:gap-5">
        <Link to={href} className="block w-32 shrink-0 overflow-hidden sm:w-40">
          <MediaImage
            media={article.heroMedia}
            variant="thumbnail"
            mediaPath={article.heroImage}
            alt={resolveAltText(article.heroMedia, article.title)}
            width={400}
            height={400}
            aspect={1}
            sizes="(min-width: 640px) 160px, 128px"
            className="aspect-square w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        </Link>
        <div className="flex flex-col justify-center">
          {topic && <span className="eyebrow">{topic.name}</span>}
          <h3 className="mt-1.5 font-serif text-lg font-semibold leading-snug text-charcoal sm:text-xl">
            <Link to={href} className="transition-colors hover:text-burgundy-600">
              {article.title}
            </Link>
          </h3>
          <div className="mt-2 text-xs text-charcoal-600">
            {author?.name} &middot; {formatShortDate(article.publishDate)}
          </div>
        </div>
      </article>
    )
  }

  if (variant === 'compact') {
    return (
      <article className="border-t border-taupe-200 py-4 first:border-t-0 first:pt-0">
        <h4 className="font-serif text-base font-semibold leading-snug text-charcoal">
          <Link to={href} className="transition-colors hover:text-burgundy-600">
            {article.title}
          </Link>
        </h4>
        <div className="mt-1.5 text-xs text-charcoal-600">{formatShortDate(article.publishDate)}</div>
      </article>
    )
  }

  // default grid card
  return (
    <article className="group flex flex-col">
      <Link to={href} className="block overflow-hidden">
        <MediaImage
          media={article.heroMedia}
          variant="card"
          mediaPath={article.heroImage}
          alt={resolveAltText(article.heroMedia, article.title)}
          width={800}
          height={533}
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
          className="aspect-[3/2] w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
      </Link>
      <div className="mt-4 flex flex-1 flex-col">
        {topic && (
          <Link to={`/topics/${topic.slug}`} className="eyebrow">
            {topic.name}
          </Link>
        )}
        <h3 className="mt-2 font-serif text-xl font-semibold leading-snug text-charcoal">
          <Link to={href} className="transition-colors hover:text-burgundy-600">
            {article.title}
          </Link>
        </h3>
        <p className="mt-2 line-clamp-2 text-sm text-charcoal-600">{article.excerpt}</p>
        <div className="mt-3 text-xs text-charcoal-600">
          {author?.name} &middot; {formatShortDate(article.publishDate)}
        </div>
      </div>
    </article>
  )
}
