import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Globe, ArrowRight } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { fetchAuthorBySlug } from '../api/taxonomies'
import { fetchArticles } from '../api/articles'
import { resolveImage } from '../utils/media'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ArticleCard from '../components/cards/ArticleCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import NotFoundPage from './NotFoundPage'

// Minimal schema.org Person structured data for the byline — built only
// from fields the author profile actually carries.
function useAuthorStructuredData(author, canonicalUrl) {
  useEffect(() => {
    if (!author) return
    const data = {
      '@context': 'https://schema.org',
      '@type': 'Person',
      name: author.name,
      url: canonicalUrl,
      ...(author.role ? { jobTitle: author.role } : {}),
      ...(author.photo ? { image: resolveImage(author.photo, { width: 400, height: 400 }) } : {}),
      ...(author.website || author.social?.linkedin || author.social?.twitter
        ? {
            sameAs: [
              author.website,
              author.social?.linkedin && `https://linkedin.com/in/${author.social.linkedin}`,
              author.social?.twitter && `https://twitter.com/${author.social.twitter}`,
            ].filter(Boolean),
          }
        : {}),
    }
    let el = document.head.querySelector('script[data-author-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-author-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [author, canonicalUrl])
}

export default function AuthorProfilePage() {
  const { slug } = useParams()
  const [author, setAuthor] = useState(undefined)
  const [articles, setArticles] = useState([])
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setAuthor(undefined)
    setError(null)
    setPage(1)

    fetchAuthorBySlug(slug)
      .then((data) => {
        if (!active) return
        setAuthor(data)
      })
      .catch(() => active && setError('Something went wrong loading this profile. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  useEffect(() => {
    if (!author) return
    let active = true
    fetchArticles({ author: slug, page, pageSize: 9 })
      .then((res) => {
        if (!active) return
        setArticles(res.items)
        setPagination(res.pagination)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [author, slug, page])

  const canonicalUrl = `https://womenshapingfutures.org/authors/${slug}`

  useSeo(
    author
      ? {
          title: author.seo?.title || `${author.name} | Women Shaping Futures`,
          description: author.seo?.description || author.shortBio,
          canonical: author.seo?.canonical || canonicalUrl,
          image: author.photo ? resolveImage(author.photo, { width: 1200, height: 630 }) : undefined,
          robots: author.seo?.robots,
        }
      : {},
  )

  useAuthorStructuredData(author, canonicalUrl)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this profile" description={error} /></div>
  if (author === undefined) return <PageLoader />
  if (author === null) return <NotFoundPage />

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Authors', to: '/authors' }, { label: author.name }]} />
          <div className="mt-6 flex flex-col items-start gap-6 sm:flex-row sm:items-center">
            <MediaImage media={author.photoMedia} variant="card" mediaPath={author.photo} alt={author.name} width={200} height={200} aspect={1} className="h-28 w-28 rounded-full object-cover" />
            <div>
              <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{author.name}</h1>
              {author.role && <p className="mt-1 text-base text-charcoal-600">{author.role}</p>}
              {(author.location || author.country) && (
                <p className="mt-1 text-sm text-charcoal-600">{author.location || author.country?.name}</p>
              )}
              {author.topics?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {author.topics.map((t) => (
                    <Link key={t.slug} to={`/topics/${t.slug}`} className="bg-taupe-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600 hover:bg-taupe-200">
                      {t.name}
                    </Link>
                  ))}
                </div>
              )}
              {(author.website || author.social?.linkedin || author.social?.twitter || author.social?.instagram) && (
                <div className="mt-3 flex gap-4">
                  {author.website && (
                    <a href={author.website} target="_blank" rel="noreferrer" aria-label="Website" className="text-charcoal-600 hover:text-burgundy-600">
                      <Globe size={17} />
                    </a>
                  )}
                  {author.social.linkedin && (
                    <a href={`https://linkedin.com/in/${author.social.linkedin}`} target="_blank" rel="noreferrer" aria-label="LinkedIn" className="text-charcoal-600 hover:text-burgundy-600">
                      <SocialIcon name="linkedin" size={17} />
                    </a>
                  )}
                  {author.social.twitter && (
                    <a href={`https://twitter.com/${author.social.twitter}`} target="_blank" rel="noreferrer" aria-label="Twitter" className="text-charcoal-600 hover:text-burgundy-600">
                      <SocialIcon name="twitter" size={17} />
                    </a>
                  )}
                  {author.social.instagram && (
                    <a href={`https://instagram.com/${author.social.instagram}`} target="_blank" rel="noreferrer" aria-label="Instagram" className="text-charcoal-600 hover:text-burgundy-600">
                      <SocialIcon name="instagram" size={17} />
                    </a>
                  )}
                </div>
              )}
              {author.person && (
                <Link to={`/people/${author.person.slug}`} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-burgundy-600 hover:underline">
                  View profile <ArrowRight size={14} />
                </Link>
              )}
            </div>
          </div>

          {author.bio?.length > 0 && (
            <div className="mt-6 max-w-2xl">
              <ArticleContent blocks={author.bio} />
            </div>
          )}
        </div>
      </div>

      <div className="container-editorial py-14">
        <p className="eyebrow mb-6">{pagination?.totalItems ?? articles.length} articles by {author.name}</p>
        {articles.length ? (
          <>
            <div className="grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
              {articles.map((a) => (
                <ArticleCard key={a.id} article={a} />
              ))}
            </div>
            {pagination && pagination.totalPages > 1 && (
              <div className="mt-10 flex items-center justify-center gap-4">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-40"
                >
                  Previous
                </button>
                <span className="text-xs text-charcoal-600">
                  Page {pagination.page} of {pagination.totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= pagination.totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <EmptyState title="No published articles yet" />
        )}
      </div>
    </div>
  )
}
