import { Link } from 'react-router-dom'
import CloudinaryImage from '../ui/CloudinaryImage'
import { getAuthorBySlug } from '../../mock/authors'
import { getTopicBySlug } from '../../mock/topics'
import { formatShortDate } from '../../utils/format'

/**
 * variant: 'lead' | 'secondary' | 'horizontal' | 'compact' | 'grid'
 * Article URLs are flat: /{slug} — never /articles/{slug}.
 */
export default function ArticleCard({ article, variant = 'grid' }) {
  if (!article) return null
  const author = getAuthorBySlug(article.authorSlug)
  const topic = getTopicBySlug(article.topicSlugs?.[0])
  const href = `/${article.slug}`

  if (variant === 'lead') {
    return (
      <article className="group relative">
        <Link to={href} className="block overflow-hidden">
          <CloudinaryImage
            publicId={article.heroImage}
            alt={article.heroImageAlt}
            width={1400}
            height={933}
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
            <span>{article.readingTime} min read</span>
          </div>
        </div>
      </article>
    )
  }

  if (variant === 'horizontal') {
    return (
      <article className="group flex gap-4 sm:gap-5">
        <Link to={href} className="block w-32 shrink-0 overflow-hidden sm:w-40">
          <CloudinaryImage
            publicId={article.heroImage}
            alt={article.heroImageAlt}
            width={400}
            height={400}
            aspect={1}
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
        <CloudinaryImage
          publicId={article.heroImage}
          alt={article.heroImageAlt}
          width={800}
          height={533}
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
