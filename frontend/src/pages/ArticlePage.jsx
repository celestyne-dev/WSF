import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Clock, Sparkles } from 'lucide-react'
import { fetchArticleBySlug, fetchArticles, fetchRelatedArticles } from '../api/articles'
import { fetchPersonBySlug } from '../api/people'
import { resolveImage, resolveMediaImage } from '../utils/media'
import { buildArticleStructuredData } from '../utils/articleStructuredData'
import { formatDate } from '../utils/format'
import { resolveReadingTime } from '../utils/readingTime'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ShareBar from '../components/ui/ShareBar'
import ArticleContent from '../components/article/ArticleContent'
import SponsorPlacementStrip from '../components/sponsors/SponsorPlacementStrip'
import ArticleCard from '../components/cards/ArticleCard'
import SaveButton from '../components/account/SaveButton'
import PersonCard from '../components/cards/PersonCard'
import NotFoundPage from './NotFoundPage'

const SITE_ORIGIN = 'https://womenshapingfutures.org'

// A ghost/text-only Save control for the lighter article byline row —
// same SaveButton component/behavior underneath, just restyled via its
// optional `className` prop so it reads as a lightweight action next to
// ShareBar rather than a bordered toolbar button.
const BYLINE_SAVE_BUTTON_CLASS =
  'inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-charcoal-600 transition-colors hover:text-burgundy-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy-500 disabled:cursor-not-allowed disabled:opacity-60'

// Subtle, non-alarming editorial transparency notice — shown only when an
// editor has explicitly enabled it (article.aiDisclosureRequired) and
// written the disclosure copy themselves. Never generated automatically;
// see AdminArticleEditor's "AI / editorial transparency" section.
function AiDisclosureNotice({ text }) {
  if (!text) return null
  return (
    <div className="mt-6 flex max-w-[720px] items-start gap-2 border border-taupe-200 bg-taupe-100/50 px-4 py-2.5 text-xs text-charcoal-600">
      <Sparkles size={14} className="mt-0.5 shrink-0 text-charcoal-600/60" />
      <p>
        <span className="font-semibold text-charcoal-600/90">Generative AI disclosure. </span>
        {text}
      </p>
    </div>
  )
}

// Valid schema.org Article structured data for a published public article —
// same script[data-X-structured-data] create/update/cleanup-on-unmount
// pattern as useEventStructuredData/useResourceStructuredData/
// useJobStructuredData. The actual data shape lives in the pure, DOM-free
// buildArticleStructuredData() (utils/articleStructuredData.js) so it can
// be unit-tested without a DOM; this hook only owns the <script> mechanics.
function useArticleStructuredData(article, canonicalUrl, imageUrl) {
  const siteName = useSelector((s) => s.site.settings?.site?.name) || 'Women Shaping Futures'
  const siteUrl = useSelector((s) => s.site.settings?.site?.url)
  const siteLogo = useSelector((s) => s.site.settings?.branding?.logo)
  const siteLogoUrl = siteLogo ? resolveMediaImage(siteLogo, { variant: 'card', width: 512, height: 512 }).src : undefined

  useEffect(() => {
    const data = buildArticleStructuredData(article, canonicalUrl, {
      imageUrl,
      siteName,
      siteUrl,
      siteLogoUrl,
      authorBaseUrl: `${SITE_ORIGIN}/authors`,
    })
    if (!data) return

    let el = document.head.querySelector('script[data-article-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-article-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [article, canonicalUrl, imageUrl, siteName, siteUrl, siteLogoUrl])
}

export default function ArticlePage() {
  const { slug } = useParams()
  const [article, setArticle] = useState(undefined)
  const [relatedPerson, setRelatedPerson] = useState(null)
  const [related, setRelated] = useState([])
  const [relatedArticlesBySlug, setRelatedArticlesBySlug] = useState({})
  const [nextArticle, setNextArticle] = useState(null)
  const [popular, setPopular] = useState([])
  // Reported by SponsorPlacementStrip itself (see its own
  // onAvailabilityChange docstring) — never independently re-fetched or
  // re-derived here. Used only to decide whether the sidebar column is
  // worth reserving layout space for at all.
  const [hasSponsorSidebar, setHasSponsorSidebar] = useState(false)

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

  const canonicalUrl = `${SITE_ORIGIN}/${slug}`
  // The single effective canonical this page commits to everywhere it
  // appears (the <link rel="canonical">, og:url, and the JSON-LD url/
  // mainEntityOfPage.@id below) — an editor-supplied CMS canonical
  // override always wins over the womenshapingfutures.org/{slug}
  // fallback, and every one of those four places must agree.
  const effectiveCanonicalUrl = article?.seo?.canonical || canonicalUrl

  // Priority for the social-share image: an explicit SEO/OG image the
  // editor picked (article.seo.ogImage, resolved server-side from
  // seo.ogImageMediaId — see ArticleSchema.get_seo) wins over the hero
  // image — and its alt text must come from that SAME image, never
  // cross-matched with the hero's alt text when the explicit image has
  // none of its own (an editor leaving alt blank on the OG image is a
  // real "no alt" case, not a reason to borrow an unrelated photo's alt).
  const hasExplicitOgImage = !!article?.seo?.ogImage
  const socialImagePath = hasExplicitOgImage ? article.seo.ogImage : article?.heroImage || null
  const socialImageAlt = hasExplicitOgImage ? article.seo.ogImageAlt || undefined : article?.heroImageAlt || undefined
  const socialImageUrl = socialImagePath ? resolveImage(socialImagePath, { width: 1200, height: 630 }) : undefined

  useSeo(
    article
      ? {
          title: article.seo?.title || article.title,
          description: article.seo?.description || article.excerpt,
          canonical: effectiveCanonicalUrl,
          image: socialImageUrl,
          imageAlt: socialImageAlt,
          robots: article.seo?.robots,
          type: 'article',
        }
      : {},
  )

  useArticleStructuredData(article, effectiveCanonicalUrl, socialImageUrl)

  useEffect(() => {
    if (article) trackEvent('article_view', { articleSlug: article.slug, topicSlugs: article.topicSlugs })
  }, [article])

  if (article === undefined) return <PageLoader />
  if (article === null) return <NotFoundPage />

  const author = article.author
  const coAuthors = article.coAuthors || []
  const topic = article.topic
  const hasSidebar = popular.length > 0 || hasSponsorSidebar

  return (
    <article>
      <div className="container-editorial pt-6">
        <Breadcrumb items={topic ? [{ label: 'Stories', to: '/topics' }, { label: topic.name, to: `/topics/${topic.slug}` }, { label: article.title }] : [{ label: article.title }]} />
      </div>

      {/* Aligned to the same centered max-w-[1064px] composition the
          article body/sidebar group below uses, so the header's left
          edge lines up with the body's left edge on desktop — the inner
          920px wrapper controls content width only and is no longer
          separately centered. */}
      <header className="container-editorial mt-8">
        <div className="mx-auto max-w-[1064px]">
          <div className="max-w-[920px]">
            {topic && (
              <Link to={`/topics/${topic.slug}`} className="eyebrow">
                {topic.name}
              </Link>
            )}
            <h1 className="mt-4 max-w-[820px] font-serif text-[2.75rem] font-semibold leading-[1.05] text-charcoal sm:text-[3.5rem] lg:text-[3.75rem]">
              {article.title}
            </h1>
            {article.subtitle && (
              <p className="mt-5 max-w-[640px] font-serif text-xl italic leading-relaxed text-charcoal-600 sm:text-2xl">{article.subtitle}</p>
            )}

            {article.isSponsored && (article.sponsorRecord || article.sponsor) && (
              <div className="mt-5 flex items-center gap-2 border border-dashed border-taupe-300 bg-blush-50 px-4 py-2 text-xs text-charcoal-600">
                <span className="font-semibold uppercase tracking-wide text-burgundy-600">
                  {article.sponsorRecord?.disclosureLabel || 'Sponsored'}
                </span>
                <span>
                  {article.sponsorRecord
                    ? article.sponsorRecord.publicName || article.sponsorRecord.organization?.name
                    : article.sponsor?.disclosure}
                </span>
              </div>
            )}

            {/* Byline + actions — a single light rule above and below, never
                a filled "toolbar" box. Author info first on every
                breakpoint; actions sit opposite on desktop and move
                cleanly beneath on mobile instead of compressing. */}
            <div className="mt-8 flex flex-col gap-5 border-y border-taupe-200 py-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                {author && (
                  <MediaImage media={author.photoMedia} variant="thumbnail" mediaPath={author.photo} alt={author.name} width={96} height={96} aspect={1} className="h-12 w-12 rounded-full object-cover" />
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
                  {author?.role && <p className="text-xs text-charcoal-600/70">{author.role}</p>}
                  <p className="mt-0.5 flex items-center gap-2 text-charcoal-600">
                    <span>{formatDate(article.publishDate)}</span>
                    <span aria-hidden="true">&middot;</span>
                    <span className="inline-flex items-center gap-1">
                      <Clock size={13} /> {resolveReadingTime(article)} min read
                    </span>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <SaveButton contentType="article" contentId={article.id} className={BYLINE_SAVE_BUTTON_CLASS} />
                <span aria-hidden="true" className="hidden h-5 w-px bg-taupe-300 sm:block" />
                <ShareBar title={article.title} url={canonicalUrl} trackEventName="article_share_click" trackPayload={{ articleSlug: article.slug }} />
              </div>
            </div>

            {article.aiDisclosureRequired && <AiDisclosureNotice text={article.aiDisclosureText} />}
          </div>
        </div>
      </header>

      {/* Hero — wider than the reading column but deliberately capped
          well short of the full container, so it reads as a considered
          editorial image rather than a dominating banner. */}
      <div className="container-editorial mt-10">
        <div className="mx-auto max-w-[1120px]">
          <MediaImage
            media={article.heroMedia}
            variant="hero"
            mediaPath={article.heroImage}
            alt={article.heroImageAlt}
            width={1600}
            height={900}
            aspect={16 / 9}
            priority
            className="aspect-[16/9] max-h-[260px] w-full object-cover sm:max-h-[380px] lg:max-h-[480px]"
          />
          {(article.heroImageCaption || article.heroImageCredit) && (
            <p className="mt-3 text-sm text-charcoal-600">
              {article.heroImageCaption}
              {article.heroImageCredit && <span className="ml-1 text-charcoal-600/60">— {article.heroImageCredit}</span>}
            </p>
          )}
        </div>
      </div>

      {/* Reading column + sidebar, centered as one group within the site
          container. The `minmax(0,720px)` track caps the body at 720px
          even inside the wider container, so it never grows to fill the
          leftover width the way a plain two-column grid would — that
          leftover is exactly what used to read as "pushed left." When
          there's no sidebar content at all, this collapses to a single
          centered reading column with nothing reserved on the right; the
          `<aside>` itself stays mounted in both cases (SponsorPlacementStrip
          is never unmounted/remounted by this toggle) so its own fetch
          only ever runs once. */}
      <div className="container-editorial mt-12">
        <div className={hasSidebar ? 'mx-auto max-w-[1064px] lg:grid lg:grid-cols-[minmax(0,720px)_280px] lg:gap-16' : 'mx-auto max-w-reading'}>
          <div>
            <ArticleContent variant="article" blocks={article.content} relatedArticlesBySlug={relatedArticlesBySlug} />

            {relatedPerson && (
              <div className="my-14 border border-taupe-200 bg-ivory p-6 sm:p-7">
                <p className="eyebrow mb-3">Featured in this story</p>
                <div className="max-w-[220px]">
                  <PersonCard person={relatedPerson} />
                </div>
              </div>
            )}

            {nextArticle && (
              <div className="mt-16 border-t-2 border-charcoal pt-8">
                <p className="eyebrow mb-3">Up next</p>
                <Link to={`/${nextArticle.slug}`} className="font-serif text-2xl font-semibold leading-snug text-charcoal transition-colors hover:text-burgundy-600 sm:text-3xl">
                  {nextArticle.title} &rarr;
                </Link>
                {(nextArticle.topic?.name || nextArticle.publishDate) && (
                  <p className="mt-3 text-sm text-charcoal-600">
                    {nextArticle.topic?.name}
                    {nextArticle.topic?.name && nextArticle.publishDate && <span aria-hidden="true"> &middot; </span>}
                    {nextArticle.publishDate && formatDate(nextArticle.publishDate)}
                  </p>
                )}
              </div>
            )}
          </div>

          <aside className={hasSidebar ? 'mt-14 space-y-10 lg:mt-0 lg:self-start lg:sticky lg:top-28' : 'mt-14 space-y-10'}>
            <SponsorPlacementStrip placementKey="article_sidebar" layout="stack" onAvailabilityChange={setHasSponsorSidebar} />
            {popular.length > 0 && (
              <div>
                <p className="eyebrow mb-4">More on WSF</p>
                {/* ArticleCard's own "compact" variant already supplies
                    the subtle divider between items (border-t, with
                    first:border-t-0 on the true first child) — rendered
                    as direct siblings here, unwrapped, so that first-child
                    rule still resolves against the real list position
                    rather than a single-item wrapper. */}
                {popular.map((a) => (
                  <ArticleCard key={a.id} article={a} variant="compact" />
                ))}
              </div>
            )}
          </aside>
        </div>
      </div>

      {related.length > 0 && (
        <div className="container-editorial mt-20 border-t border-taupe-200 py-16">
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
