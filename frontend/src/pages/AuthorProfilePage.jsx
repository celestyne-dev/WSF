import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Globe, ArrowRight } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { fetchAuthorBySlug } from '../api/taxonomies'
import { fetchArticles } from '../api/articles'
import { resolveImage, resolveAltText } from '../utils/media'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ArticleCard from '../components/cards/ArticleCard'
import SourceReferences from '../components/article/SourceReferences'
import CredentialsList from '../components/article/CredentialsList'
import { buildAuthorProfilePageStructuredData } from '../utils/profileStructuredData'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import NotFoundPage from './NotFoundPage'
import ResourceCard from '../components/cards/ResourceCard'
import LearningProgramCard from '../components/cards/LearningProgramCard'
import { mapResource } from '../api/resources'
import { mapLearningProgram } from '../api/learning'
import { trackEvent } from '../utils/analytics'
import { authorFirstName, authorStatItems, hasItems } from '../utils/authorAuthority'

// schema.org ProfilePage (mainEntity: the Author's Person identity) — the
// data shape is the pure buildAuthorProfilePageStructuredData() (utils/
// profileStructuredData.js, mirroring spa_shell.py's _build_author_json_ld);
// this hook only owns the <script>, reusing the server's
// data-author-structured-data tag rather than adding a second one.
function useAuthorStructuredData(author, canonicalUrl) {
  useEffect(() => {
    if (!author) return
    const data = buildAuthorProfilePageStructuredData(author, canonicalUrl, {
      imageUrl: author.photo ? resolveImage(author.photo, { width: 400, height: 400 }) : undefined,
    })
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
        if (data) trackEvent('author_profile_view', { authorSlug: data.slug })
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
  // One effective canonical for useSeo, the ProfilePage JSON-LD and the
  // breadcrumb — the same resolved value spa_shell.py's _author_meta gives
  // all three server-side (an editor's seo.canonical override, else the
  // default /authors/{slug}).
  const effectiveCanonicalUrl = author?.seo?.canonical || canonicalUrl

  useSeo(
    author
      ? {
          title: author.seo?.title || `${author.name} | Women Shaping Futures`,
          description: author.seo?.description || author.shortBio,
          canonical: effectiveCanonicalUrl,
          image: author.photo ? resolveImage(author.photo, { width: 1200, height: 630 }) : undefined,
          robots: author.seo?.robots,
        }
      : {},
  )

  useAuthorStructuredData(author, effectiveCanonicalUrl)
  useBreadcrumbStructuredData(author ? [{ label: 'Authors', to: '/authors' }, { label: author.name }] : null, effectiveCanonicalUrl)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this profile" description={error} /></div>
  if (author === undefined) return <PageLoader />
  if (author === null) return <NotFoundPage />

  const firstName = authorFirstName(author.name)
  const stats = authorStatItems(author.authority?.counts)
  const programs = (author.authority?.learningPrograms || []).map(mapLearningProgram)
  const tools = (author.authority?.resources || []).map(mapResource)

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Authors', to: '/authors' }, { label: author.name }]} />
          <div className="mt-6 flex flex-col items-start gap-6 sm:flex-row sm:items-center">
            <MediaImage media={author.photoMedia} variant="card" mediaPath={author.photo} alt={resolveAltText(author.photoMedia, author.name)} width={200} height={200} aspect={1} sizes="112px" className="h-28 w-28 rounded-full object-cover" />
            <div>
              <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{author.name}</h1>
              {author.headline && <p className="mt-1 text-base font-medium text-plum-600">{author.headline}</p>}
              {(author.role || author.location || author.country) && (
                <p className="mt-1 text-sm text-charcoal-600">
                  {[author.role, author.location || author.country?.name].filter(Boolean).join(' · ')}
                </p>
              )}
              {author.topics?.length > 0 && (
                <ul aria-label="Areas of expertise" className="mt-3 flex flex-wrap gap-2">
                  {author.topics.map((t) => (
                    <li key={t.slug}>
                      <Link to={`/topics/${t.slug}`} className="inline-block bg-taupe-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600 hover:bg-taupe-200">
                        {t.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {stats.length > 0 && (
                <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  {stats.map((stat) => (
                    <div key={stat.label} className="flex items-baseline gap-1.5">
                      <dt className="sr-only">{stat.label}</dt>
                      <dd className="font-serif text-xl font-semibold text-charcoal">{stat.value}</dd>
                      <span className="text-charcoal-600">{stat.label}</span>
                    </div>
                  ))}
                </dl>
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
                  View full profile <ArrowRight size={14} />
                </Link>
              )}
            </div>
          </div>

        </div>
      </div>

      <div className="container-editorial space-y-14 py-14">
        {author.bio?.length > 0 && (
          <section aria-labelledby="author-about" className="max-w-2xl">
            <h2 id="author-about" className="font-serif text-2xl font-semibold text-charcoal">About {firstName}</h2>
            <div className="mt-4">
              <ArticleContent blocks={author.bio} />
            </div>
          </section>
        )}

        {hasItems(programs) && (
          <section aria-labelledby="author-learning">
            <h2 id="author-learning" className="font-serif text-2xl font-semibold text-charcoal">Learn with {firstName}</h2>
            <ul className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {programs.map((program) => (
                <li key={program.id} onClickCapture={() => trackEvent('author_course_click', { authorSlug: author.slug, programSlug: program.slug })}>
                  <LearningProgramCard program={program} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {hasItems(tools) && (
          <section aria-labelledby="author-resources">
            <h2 id="author-resources" className="font-serif text-2xl font-semibold text-charcoal">Career tools by {firstName}</h2>
            <ul className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {tools.map((resource) => (
                <li key={resource.id} onClickCapture={() => trackEvent('author_resource_click', { authorSlug: author.slug, resourceSlug: resource.slug })}>
                  <ResourceCard resource={resource} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {(articles.length > 0 || page > 1) && (
        <section aria-labelledby="author-articles">
        <h2 id="author-articles" className="font-serif text-2xl font-semibold text-charcoal">Latest articles</h2>
        <p className="eyebrow mb-6 mt-2">{pagination?.totalItems ?? articles.length} articles by {author.name}</p>
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
          <EmptyState title="No more articles" />
        )}
        </section>
        )}

        {author.credentials?.length > 0 && (
          <div className="max-w-2xl">
            <CredentialsList credentials={author.credentials} id="author-credentials" />
          </div>
        )}

        {author.sources?.length > 0 && (
          <div className="max-w-2xl">
            <SourceReferences sources={author.sources} id="author-sources" />
          </div>
        )}
      </div>
    </div>
  )
}
