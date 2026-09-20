import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Link as LinkIcon, Clock } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { toast } from 'react-toastify'
import { fetchArticleBySlug } from '../api/articles'
import { getAuthorBySlug } from '../mock/authors'
import { getTopicBySlug } from '../mock/topics'
import { getPersonBySlug } from '../mock/people'
import { articles as allArticles, getArticleBySlug } from '../mock/articles'
import { resolveImage } from '../utils/media'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ArticleCard from '../components/cards/ArticleCard'
import PersonCard from '../components/cards/PersonCard'
import NotFoundPage from './NotFoundPage'

function ShareBar({ title, url }) {
  const encodedUrl = encodeURIComponent(url)
  const encodedTitle = encodeURIComponent(title)
  const links = [
    { icon: 'facebook', label: 'Share on Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}` },
    { icon: 'twitter', label: 'Share on X', href: `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedTitle}` },
    { icon: 'linkedin', label: 'Share on LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}` },
  ]
  return (
    <div className="flex items-center gap-3">
      {links.map(({ icon, label, href }) => (
        <a
          key={label}
          href={href}
          target="_blank"
          rel="noreferrer"
          aria-label={label}
          className="flex h-9 w-9 items-center justify-center border border-taupe-300 text-charcoal transition-colors hover:border-burgundy-500 hover:text-burgundy-600"
        >
          <SocialIcon name={icon} size={16} />
        </a>
      ))}
      <button
        type="button"
        aria-label="Copy link"
        onClick={() => {
          navigator.clipboard?.writeText(url)
          toast.success('Link copied to clipboard')
        }}
        className="flex h-9 w-9 items-center justify-center border border-taupe-300 text-charcoal transition-colors hover:border-burgundy-500 hover:text-burgundy-600"
      >
        <LinkIcon size={16} />
      </button>
    </div>
  )
}

export default function ArticlePage() {
  const { slug } = useParams()
  const [article, setArticle] = useState(undefined)

  useEffect(() => {
    let active = true
    setArticle(undefined)
    fetchArticleBySlug(slug).then((data) => {
      if (active) setArticle(data)
    })
    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = `https://womenshapingfutures.org/${slug}`

  useSeo(
    article
      ? {
          title: article.seo?.title || article.title,
          description: article.seo?.description || article.excerpt,
          canonical: article.seo?.canonical || canonicalUrl,
          image: resolveImage(article.seo?.ogImage || article.heroImage, { width: 1200, height: 630 }),
          robots: article.seo?.robots,
        }
      : {},
  )

  if (article === undefined) return <PageLoader />
  if (article === null) return <NotFoundPage />

  const author = getAuthorBySlug(article.authorSlug)
  const coAuthors = (article.coAuthorSlugs || []).map((s) => getAuthorBySlug(s)).filter(Boolean)
  const topic = getTopicBySlug(article.topicSlugs?.[0])
  const related = (article.relatedArticleSlugs || []).map((s) => getArticleBySlug(s)).filter(Boolean)
  const relatedPerson = article.relatedPersonSlugs?.[0] ? getPersonBySlug(article.relatedPersonSlugs[0]) : null
  const currentIndex = allArticles.findIndex((a) => a.slug === article.slug)
  const nextArticle = allArticles[(currentIndex + 1) % allArticles.length]
  const popular = allArticles.filter((a) => a.slug !== article.slug).slice(0, 5)

  return (
    <article>
      <div className="container-editorial pt-6">
        <Breadcrumb items={topic ? [{ label: 'Stories', to: '/topics' }, { label: topic.name, to: `/topics/${topic.slug}` }, { label: article.title }] : [{ label: article.title }]} />
      </div>

      <header className="container-editorial mt-6 max-w-reading">
        {topic && (
          <Link to={`/topics/${topic.slug}`} className="eyebrow">
            {topic.name}
          </Link>
        )}
        <h1 className="mt-3 font-serif text-4xl font-semibold leading-[1.1] text-charcoal sm:text-5xl">{article.title}</h1>
        {article.subtitle && <p className="mt-4 font-serif text-xl italic leading-snug text-charcoal-600">{article.subtitle}</p>}

        {article.isSponsored && article.sponsor && (
          <div className="mt-5 flex items-center gap-2 border border-dashed border-taupe-300 bg-blush-50 px-4 py-2 text-xs text-charcoal-600">
            <span className="font-semibold uppercase tracking-wide text-burgundy-600">Sponsored</span>
            <span>{article.sponsor.disclosure}</span>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-y border-taupe-200 py-4">
          <div className="flex items-center gap-3">
            {author && (
              <MediaImage mediaPath={author.photo} alt={author.name} width={96} height={96} aspect={1} className="h-11 w-11 rounded-full object-cover" />
            )}
            <div className="text-sm">
              <p className="font-semibold text-charcoal">
                By{' '}
                {author && (
                  <Link to={`/authors/${author.slug}`} className="hover:text-burgundy-600">
                    {author.name}
                  </Link>
                )}
                {coAuthors.map((c) => (
                  <span key={c.slug}>
                    {' '}
                    &amp;{' '}
                    <Link to={`/authors/${c.slug}`} className="hover:text-burgundy-600">
                      {c.name}
                    </Link>
                  </span>
                ))}
              </p>
              <p className="mt-0.5 flex items-center gap-2 text-charcoal-600">
                <span>{formatDate(article.publishDate)}</span>
                <span aria-hidden="true">&middot;</span>
                <span className="inline-flex items-center gap-1">
                  <Clock size={13} /> {article.readingTime} min read
                </span>
              </p>
            </div>
          </div>
          <ShareBar title={article.title} url={canonicalUrl} />
        </div>
      </header>

      <div className="container-editorial mt-8 max-w-content">
        <MediaImage mediaPath={article.heroImage} alt={article.heroImageAlt} width={1600} height={1000} priority className="w-full object-cover" />
        {(article.heroImageCaption || article.heroImageCredit) && (
          <p className="mt-2 text-sm text-charcoal-600">
            {article.heroImageCaption} {article.heroImageCredit && <span className="text-charcoal-600/70">— {article.heroImageCredit}</span>}
          </p>
        )}
      </div>

      <div className="container-editorial mt-10 grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          <ArticleContent blocks={article.content} />

          {relatedPerson && (
            <div className="my-10 border border-taupe-200 p-5">
              <p className="eyebrow mb-3">Featured in this story</p>
              <div className="max-w-[220px]">
                <PersonCard person={relatedPerson} />
              </div>
            </div>
          )}

          <div className="mt-12 border-t border-taupe-200 pt-8">
            <p className="eyebrow mb-2">Up next</p>
            <Link to={`/${nextArticle.slug}`} className="font-serif text-2xl font-semibold text-charcoal transition-colors hover:text-burgundy-600">
              {nextArticle.title} &rarr;
            </Link>
          </div>
        </div>

        <aside className="space-y-10">
          <div className="flex h-64 items-center justify-center border border-dashed border-taupe-300 bg-taupe-100/60 text-xs uppercase tracking-wide text-charcoal-600/60">
            Advertisement — article_sidebar
          </div>
          <div>
            <p className="eyebrow mb-4">Popular on WSF</p>
            {popular.map((a) => (
              <ArticleCard key={a.id} article={a} variant="compact" />
            ))}
          </div>
        </aside>
      </div>

      {related.length > 0 && (
        <div className="container-editorial mt-16 border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">More stories you’ll like</p>
          <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-3">
            {related.map((a) => (
              <ArticleCard key={a.id} article={a} />
            ))}
          </div>
        </div>
      )}
    </article>
  )
}
