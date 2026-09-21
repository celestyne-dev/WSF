import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Link as LinkIcon, Clock } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { toast } from 'react-toastify'
import { fetchArticleBySlug, fetchArticles, fetchRelatedArticles } from '../api/articles'
import { fetchPersonBySlug } from '../api/people'
import { resolveImage } from '../utils/media'
import { formatDate } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ArticleCard from '../components/cards/ArticleCard'
import PersonCard from '../components/cards/PersonCard'
import NotFoundPage from './NotFoundPage'

// LinkedIn leads the share bar — it's Women Shaping Futures' primary
// distribution channel, so sharing an article back to LinkedIn is the
// single most valuable action a reader can take after the newsletter CTA.
function ShareBar({ title, url, articleSlug }) {
  const encodedUrl = encodeURIComponent(url)
  const encodedTitle = encodeURIComponent(title)
  const links = [
    { icon: 'linkedin', label: 'Share on LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`, emphasize: true },
    { icon: 'twitter', label: 'Share on X', href: `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedTitle}` },
    { icon: 'facebook', label: 'Share on Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}` },
  ]
  return (
    <div className="flex items-center gap-3">
      {links.map(({ icon, label, href, emphasize }) => (
        <a
          key={label}
          href={href}
          target="_blank"
          rel="noreferrer"
          aria-label={label}
          onClick={() => trackEvent('article_share_click', { articleSlug, network: icon })}
          className={`flex h-9 w-9 items-center justify-center border transition-colors ${
            emphasize
              ? 'border-burgundy-500 bg-burgundy-500/10 text-burgundy-600 hover:bg-burgundy-500 hover:text-ivory'
              : 'border-taupe-300 text-charcoal hover:border-burgundy-500 hover:text-burgundy-600'
          }`}
        >
          <SocialIcon name={icon} size={16} />
        </a>
      ))}
      <button
        type="button"
        aria-label="Copy link"
        onClick={() => {
          navigator.clipboard?.writeText(url)
          trackEvent('article_share_click', { articleSlug, network: 'copy_link' })
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
  const [relatedPerson, setRelatedPerson] = useState(null)
  const [related, setRelated] = useState([])
  const [relatedArticlesBySlug, setRelatedArticlesBySlug] = useState({})
  const [nextArticle, setNextArticle] = useState(null)
  const [popular, setPopular] = useState([])

  useEffect(() => {
    let active = true
    setArticle(undefined)
    setRelatedPerson(null)
    setRelated([])
    setRelatedArticlesBySlug({})
    setNextArticle(null)
    setPopular([])

    fetchArticleBySlug(slug).then((data) => {
      if (!active) return
      setArticle(data)
      if (!data) return

      if (data.relatedPersonSlugs?.[0]) {
        fetchPersonBySlug(data.relatedPersonSlugs[0])
          .then((p) => active && setRelatedPerson(p))
          .catch(() => {})
      }

      const contentBlockSlugs = (data.content || [])
        .filter((b) => b.type === 'relatedBlock')
        .flatMap((b) => b.articleSlugs || [])
      const allSlugs = [...new Set([...(data.relatedArticleSlugs || []), ...contentBlockSlugs])]
      if (allSlugs.length) {
        fetchRelatedArticles(allSlugs)
          .then((items) => {
            if (!active) return
            setRelated(items.filter((a) => data.relatedArticleSlugs?.includes(a.slug)))
            setRelatedArticlesBySlug(Object.fromEntries(items.map((a) => [a.slug, a])))
          })
          .catch(() => {})
      }

      // No dedicated "next"/"popular" endpoint exists yet, so both are
      // derived client-side from the already-supported recent-articles list.
      fetchArticles({ pageSize: 8 })
        .then((res) => {
          if (!active) return
          const others = res.items.filter((a) => a.slug !== data.slug)
          if (others.length) setNextArticle(others[0])
          setPopular(others.slice(0, 5))
        })
        .catch(() => {})
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

  useEffect(() => {
    if (article) trackEvent('article_view', { articleSlug: article.slug, topicSlugs: article.topicSlugs })
  }, [article])

  if (article === undefined) return <PageLoader />
  if (article === null) return <NotFoundPage />

  const author = article.author
  const coAuthors = article.coAuthors || []
  const topic = article.topic

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
          <ShareBar title={article.title} url={canonicalUrl} articleSlug={article.slug} />
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
          <ArticleContent blocks={article.content} relatedArticlesBySlug={relatedArticlesBySlug} />

          {relatedPerson && (
            <div className="my-10 border border-taupe-200 p-5">
              <p className="eyebrow mb-3">Featured in this story</p>
              <div className="max-w-[220px]">
                <PersonCard person={relatedPerson} />
              </div>
            </div>
          )}

          {nextArticle && (
            <div className="mt-12 border-t border-taupe-200 pt-8">
              <p className="eyebrow mb-2">Up next</p>
              <Link to={`/${nextArticle.slug}`} className="font-serif text-2xl font-semibold text-charcoal transition-colors hover:text-burgundy-600">
                {nextArticle.title} &rarr;
              </Link>
            </div>
          )}
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
