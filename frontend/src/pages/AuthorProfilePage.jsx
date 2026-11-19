import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Globe, ArrowRight, ArrowUpRight } from 'lucide-react'
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
import { authorProfileModel } from '../utils/authorAuthority'

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

  const model = authorProfileModel(author, { articleCount: articles.length, page })
  const { firstName } = model
  const programs = (author.authority?.learningPrograms || []).map(mapLearningProgram)
  const tools = (author.authority?.resources || []).map(mapResource)
  const totalArticles = pagination?.totalItems ?? articles.length
  const show = (key) => model.sections.includes(key)

  return (
    <div>
      {/* Hero: identity and authority signals. */}
      <header className="border-b border-taupe-200 bg-cream">
        <div className="container-editorial max-w-[1240px] pb-8 pt-5">
          <div className="opacity-80">
            <Breadcrumb items={[{ label: 'Authors', to: '/authors' }, { label: author.name }]} />
          </div>
          <div
            className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center sm:gap-8 md:grid-cols-[200px_minmax(0,1fr)] md:gap-10 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-14"
          >
            {model.hasPortrait ? (
              <MediaImage
                media={author.photoMedia}
                variant="card"
                mediaPath={author.photo}
                alt={resolveAltText(author.photoMedia, `Portrait of ${author.name}`)}
                width={520}
                height={650}
                aspect={4 / 5}
                sizes="(min-width: 1024px) 260px, (min-width: 768px) 200px, (min-width: 640px) 180px, 130px"
                priority
                className="aspect-[4/5] w-[130px] rounded-lg border border-taupe-200 object-cover sm:w-full"
              />
            ) : (
              <div
                aria-hidden="true"
                className="flex aspect-[4/5] w-[130px] items-center justify-center rounded-lg border border-taupe-200 bg-ivory-200 font-serif text-4xl text-burgundy-600 sm:w-full md:text-5xl lg:text-6xl"
              >
                {model.initials}
              </div>
            )}

            <div className="min-w-0">
              <h1 className="font-serif text-[32px] font-semibold leading-[1.1] text-charcoal sm:text-4xl lg:text-[46px]">{author.name}</h1>
              {model.headline && <p className="mt-2 font-serif text-lg leading-snug text-burgundy-700 sm:text-xl">{model.headline}</p>}
              {model.roleLine && <p className="mt-2 text-sm text-charcoal-600 sm:text-base">{model.roleLine}</p>}

              {model.topics.length > 0 && (
                <div className="mt-5">
                  <p className="text-[11px] font-semibold uppercase tracking-widest2 text-charcoal-600/80">Areas of expertise</p>
                  <ul aria-label="Areas of expertise" className="mt-2 flex flex-wrap gap-2">
                    {model.topics.map((t) => (
                      <li key={t.slug}>
                        <Link
                          to={`/topics/${t.slug}`}
                          className="inline-block rounded-full border border-taupe-300 bg-ivory px-3 py-1 text-xs font-medium text-charcoal-600 transition-colors hover:border-burgundy-500 hover:text-burgundy-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy-600"
                        >
                          {t.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {model.stats.length > 0 && (
                <dl className="mt-5 inline-flex max-w-full flex-wrap border-y border-taupe-200">
                  {model.stats.map((stat, i) => (
                    <div key={stat.label} className={`flex flex-col-reverse py-2.5 pr-6 sm:pr-8 ${i > 0 ? 'border-l border-taupe-200 pl-6 sm:pl-8' : ''}`}>
                      <dt className="text-[11px] font-semibold uppercase tracking-wider text-charcoal-600">{stat.label}</dt>
                      <dd className="font-serif text-3xl font-semibold leading-none text-charcoal">{stat.value}</dd>
                    </div>
                  ))}
                </dl>
              )}

              {(model.links.length > 0 || model.person) && (
                <ul className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
                  {model.links.map((link) => (
                    <li key={link.kind}>
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 border-b border-taupe-300 pb-0.5 font-semibold text-charcoal transition-colors hover:border-burgundy-600 hover:text-burgundy-600"
                      >
                        {link.kind === 'website' ? <Globe size={15} aria-hidden="true" /> : <SocialIcon name={link.kind} size={15} />}
                        {link.label}
                        <ArrowUpRight size={13} aria-hidden="true" />
                        <span className="sr-only">(opens in a new tab)</span>
                      </a>
                    </li>
                  ))}
                  {model.person && (
                    <li>
                      <Link to={`/people/${model.person.slug}`} className="inline-flex items-center gap-1 font-semibold text-burgundy-600 hover:underline">
                        View full profile <ArrowRight size={14} aria-hidden="true" />
                      </Link>
                    </li>
                  )}
                </ul>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="container-editorial max-w-[1240px]">
        {show('profile') && (
          <div
            className={
              model.sidebar
                ? 'grid grid-cols-1 gap-12 pb-14 pt-10 lg:grid-cols-12 lg:gap-16 lg:pb-16 lg:pt-12'
                : 'pb-14 pt-10 md:grid md:grid-cols-[200px_minmax(0,1fr)] md:gap-10 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-14 lg:pb-16 lg:pt-12'
            }
          >
            {model.about && (
              <section aria-labelledby="author-about" className={model.sidebar ? 'max-w-reading lg:col-span-8' : 'max-w-reading md:col-start-2'}>
                <h2 id="author-about" className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">About {firstName}</h2>
                <div className="mt-6 text-[17px] leading-[1.75] text-charcoal-700 sm:text-lg">
                  <ArticleContent blocks={author.bio} variant="profile" />
                </div>
              </section>
            )}
            {model.credentials.length > 0 && (
              <aside className={model.sidebar ? 'lg:col-span-4' : `max-w-reading md:col-start-2 ${model.about ? 'mt-12' : ''}`}>
                <CredentialsList credentials={model.credentials} id="author-credentials" compact={model.sidebar} />
              </aside>
            )}
          </div>
        )}

        {show('learning') && (
          <section aria-labelledby="author-learning" className="border-t border-taupe-200 py-14 lg:py-16">
            <h2 id="author-learning" className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">Learn with {firstName}</h2>
            <p className="mt-2 text-sm text-charcoal-600">Courses and learning programs taught by {firstName}.</p>
            <ul className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {programs.map((program) => (
                <li key={program.id} onClickCapture={() => trackEvent('author_course_click', { authorSlug: author.slug, programSlug: program.slug })}>
                  <LearningProgramCard program={program} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {show('resources') && (
          <section aria-labelledby="author-resources" className="border-t border-taupe-200 py-14 lg:py-16">
            <h2 id="author-resources" className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">Career tools by {firstName}</h2>
            <p className="mt-2 text-sm text-charcoal-600">Practical guides, templates and toolkits created by {firstName}.</p>
            <ul className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {tools.map((resource) => (
                <li key={resource.id} onClickCapture={() => trackEvent('author_resource_click', { authorSlug: author.slug, resourceSlug: resource.slug })}>
                  <ResourceCard resource={resource} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {show('articles') && (
          <section aria-labelledby="author-articles" className="border-t border-taupe-200 py-14 lg:py-16">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="author-articles" className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">
                {page > 1 ? `Articles by ${firstName}` : 'Latest articles'}
              </h2>
              <p className="text-xs font-semibold uppercase tracking-wider text-charcoal-600">
                {totalArticles} {totalArticles === 1 ? 'article' : 'articles'}
              </p>
            </div>
            {articles.length > 0 ? (
              <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
                {articles.map((a) => (
                  <ArticleCard key={a.id} article={a} />
                ))}
              </div>
            ) : (
              <p className="mt-8 text-sm text-charcoal-600">No more articles.</p>
            )}
            {pagination && pagination.totalPages > 1 && (
              <nav aria-label={`Articles by ${author.name}`} className="mt-12 flex items-center justify-center gap-4">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-40"
                >
                  Newer articles
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
                  Older articles
                </button>
              </nav>
            )}
          </section>
        )}

        {show('sources') && (
          <div className="max-w-reading pb-14 text-sm">
            <SourceReferences sources={author.sources} id="author-sources" />
          </div>
        )}
      </div>
    </div>
  )
}
