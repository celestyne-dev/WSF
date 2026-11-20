import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Globe, ArrowRight, ArrowUpRight } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { fetchAuthorBySlug, mapAuthor } from '../api/taxonomies'
import { fetchArticles, mapArticle } from '../api/articles'
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
import { authorBootstrapState, authorProfileModel } from '../utils/authorAuthority'
import { readBootstrap, consumeBootstrap } from '../utils/bootstrap'

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
  // Hard load: the server embeds this page's public data once (spa_shell
  // _safe_public_author_payload), so the first client frame is the final
  // page with no Author/articles refetch. readBootstrap only reads the DOM
  // and checks the slug, so it is safe in this memo; the tag is removed
  // (consumeBootstrap) from the effect below. A client-side navigation to
  // another Author finds no matching tag and fetches normally.
  const bootstrap = useMemo(
    () => authorBootstrapState(readBootstrap('author', slug), { mapAuthor, mapArticle }),
    [slug],
  )
  const [author, setAuthor] = useState(() => bootstrap?.author ?? undefined)
  const [articles, setArticles] = useState(() => bootstrap?.articles ?? [])
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState(() => bootstrap?.pagination ?? null)
  const [error, setError] = useState(null)
  // Which slug's bootstrapped article page 1 has already been shown, so only
  // the very first page-1 render skips the fetch (pagination and a later
  // return to page 1 always fetch).
  const bootstrapArticlesShown = useRef(null)

  useEffect(() => {
    if (bootstrap) {
      consumeBootstrap('author')
      trackEvent('author_profile_view', { authorSlug: bootstrap.author.slug })
      return undefined
    }
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
  }, [slug, bootstrap])

  useEffect(() => {
    if (!author) return
    if (bootstrap && page === 1 && bootstrapArticlesShown.current !== slug) {
      bootstrapArticlesShown.current = slug
      return
    }
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
  }, [author, slug, page, bootstrap])

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
      {/* Hero: portrait left, identity right (stacks on mobile). Facts carry
          only real values; no headline counters. Mirrored by the server
          prerender (backend prerender.render_author_prerender). */}
      <header className="border-b border-taupe-200 bg-cream">
        <div className="container-editorial max-w-[1240px] pb-10 pt-5 lg:pb-14">
          <div className="opacity-80">
            <Breadcrumb items={[{ label: 'Authors', to: '/authors' }, { label: author.name }]} />
          </div>
          <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-[200px_minmax(0,1fr)] sm:gap-10 lg:mt-8 lg:grid-cols-[300px_minmax(0,1fr)] lg:gap-16">
            {model.hasPortrait ? (
              <MediaImage
                media={author.photoMedia}
                variant="card"
                mediaPath={author.photo}
                alt={resolveAltText(author.photoMedia, `Portrait of ${author.name}`)}
                width={600}
                height={750}
                aspect={4 / 5}
                sizes="(min-width: 1024px) 300px, (min-width: 640px) 200px, 160px"
                priority
                className="aspect-[4/5] w-[160px] rounded-media border border-taupe-200 object-cover sm:w-full"
              />
            ) : (
              <div
                aria-hidden="true"
                className="flex aspect-[4/5] w-[160px] items-center justify-center rounded-media border border-taupe-200 bg-ivory-200 font-serif text-5xl text-burgundy-600 sm:w-full lg:text-7xl"
              >
                {model.initials}
              </div>
            )}

            <div className="min-w-0 self-center">
              <h1 className="font-serif text-[36px] font-semibold leading-[1.05] text-charcoal sm:text-5xl lg:text-[60px]">{author.name}</h1>
              {model.subtitle && <p className="mt-3 font-serif text-lg leading-snug text-burgundy-700 sm:text-xl">{model.subtitle}</p>}
              {model.intro && <p className="mt-5 max-w-reading text-base leading-relaxed text-charcoal-700 sm:text-[17px]">{model.intro}</p>}

              {model.facts.length > 0 && (
                <dl className="mt-6 grid max-w-reading grid-cols-1 gap-x-8 gap-y-4 border-t border-taupe-200 pt-5 sm:grid-cols-2">
                  {model.facts.map((fact) => (
                    <div key={fact.key} className={fact.key === 'topics' ? 'sm:col-span-2' : ''}>
                      <dt className="text-[11px] font-semibold uppercase tracking-widest2 text-charcoal-600">{fact.label}</dt>
                      {fact.topics ? (
                        <dd className="mt-1 text-sm text-charcoal-700">
                          {fact.topics.map((t, i) => (
                            <span key={t.slug}>
                              {i > 0 && ', '}
                              <Link to={`/topics/${t.slug}`} className="font-medium text-charcoal underline decoration-taupe-300 underline-offset-4 hover:text-burgundy-600 hover:decoration-burgundy-600">
                                {t.name}
                              </Link>
                            </span>
                          ))}
                        </dd>
                      ) : (
                        fact.values.map((value) => (
                          <dd key={value} className="mt-1 text-sm text-charcoal-700">{value}</dd>
                        ))
                      )}
                    </div>
                  ))}
                </dl>
              )}

              {(model.links.length > 0 || model.person) && (
                <ul className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
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
        {show('about') && (
          <section aria-labelledby="author-about" className="py-14 lg:py-16">
            <div className="max-w-reading">
              <h2 id="author-about" className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">About {firstName}</h2>
              <div className="mt-6 text-[17px] leading-[1.75] text-charcoal-700 sm:text-lg [&_li_a]:text-burgundy-600 [&_li_a]:underline [&_li_a]:underline-offset-2 [&_p_a]:text-burgundy-600 [&_p_a]:underline [&_p_a]:underline-offset-2">
                <ArticleContent blocks={author.bio} variant="profile" />
              </div>
            </div>
          </section>
        )}

        {show('credentials') && (
          <div className={`pb-14 pt-4 lg:pb-16 ${show('about') ? 'border-t border-taupe-200' : ''}`}>
            <div className="max-w-reading">
              <CredentialsList credentials={model.credentials} id="author-credentials" />
            </div>
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
                Browse all of {firstName}&rsquo;s articles
              </h2>
              <p className="text-sm text-charcoal-600">
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
