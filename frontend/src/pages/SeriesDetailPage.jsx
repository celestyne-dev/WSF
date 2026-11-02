import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchSeriesBySlug } from '../api/taxonomies'
import { fetchArticles } from '../api/articles'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import { resolveImage, resolveAltText } from '../utils/media'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleCard from '../components/cards/ArticleCard'
import ArticleContent from '../components/article/ArticleContent'
import SourceReferences from '../components/article/SourceReferences'
import ProfilePreviewList from '../components/article/ProfilePreviewList'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import NotFoundPage from './NotFoundPage'

export default function SeriesDetailPage() {
  const { slug } = useParams()
  const [seriesItem, setSeriesItem] = useState(undefined)
  const [articles, setArticles] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setSeriesItem(undefined)
    setError(null)

    fetchSeriesBySlug(slug)
      .then((data) => {
        if (!active) return
        setSeriesItem(data)
        if (!data) return
        fetchArticles({ series: slug })
          .then((res) => active && setArticles(res.items))
          .catch(() => {})
      })
      .catch(() => active && setError('Something went wrong loading this series. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  useSeo(
    seriesItem
      ? {
          title: seriesItem.seo?.title || `${seriesItem.name} | Women Shaping Futures`,
          description: seriesItem.seo?.description || seriesItem.description,
          canonical: seriesItem.seo?.canonical || `https://womenshapingfutures.org/series/${seriesItem.slug}`,
          robots: seriesItem.seo?.robots,
          image: seriesItem.coverMedia ? resolveImage(seriesItem.coverMedia, { width: 1200, height: 630 }) : undefined,
        }
      : {},
  )

  useBreadcrumbStructuredData(
    seriesItem ? [{ label: 'Series', to: '/series' }, { label: seriesItem.name }] : null,
    seriesItem ? seriesItem.seo?.canonical || `https://womenshapingfutures.org/series/${seriesItem.slug}` : null,
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this series" description={error} /></div>
  if (seriesItem === undefined) return <PageLoader />
  if (seriesItem === null) return <NotFoundPage />

  // GEO Phase 4C — see TopicDetailPage: the featured story is shown once,
  // in "Start here", and dropped from this (unpaginated) first page.
  const featured = seriesItem.featuredArticle
  const stories = featured ? articles.filter((a) => a.slug !== featured.slug) : articles
  const hasDepth = seriesItem.content?.length > 0 || !!featured || seriesItem.people?.length > 0

  return (
    <div>
      {/* An editorial split hero rather than a shallow object-cover banner:
          the old layout forced every uploaded image (portrait, landscape,
          square) into a wide shallow box and cropped it to fit. Text now
          gets its own readable column instead of sitting on top of the
          image, and the image gets its own panel sized to show the full
          composition via object-contain — no new CMS field, no crop. */}
      <div className="border-b border-taupe-200">
        <div className="container-editorial py-14 lg:py-16">
          <div className="grid grid-cols-1 items-center gap-10 lg:mx-auto lg:max-w-[1220px] lg:grid-cols-[1fr_1.15fr] lg:gap-14">
            <div>
              <Breadcrumb items={[{ label: 'Series', to: '/series' }, { label: seriesItem.name }]} />
              <p className="eyebrow mt-5">Series</p>
              <h1 className="mt-2 font-serif text-4xl font-semibold leading-tight text-charcoal sm:text-5xl">{seriesItem.name}</h1>
              {seriesItem.subtitle && <p className="mt-2 text-xl text-charcoal-600">{seriesItem.subtitle}</p>}
              <p className="mt-4 max-w-md text-lg leading-relaxed text-charcoal-600">{seriesItem.description}</p>
              {seriesItem.sponsor && (
                <p className="mt-4 text-xs uppercase tracking-wide text-charcoal-600/70">Presented in partnership with {seriesItem.sponsor.name}</p>
              )}
            </div>
            {/* A fixed-height panel only at lg+ (mobile sizes to the
                image's own natural height instead, per spec, so nothing
                is ever cropped); `object-contain` lets a portrait image
                show in full, letterboxed in the panel's own background,
                while a landscape image naturally fills more of it. */}
            <div className="relative flex items-center justify-center overflow-hidden bg-cream lg:h-[520px]">
              <MediaImage
                media={seriesItem.coverMedia}
                variant="hero"
                mediaPath={seriesItem.coverImage}
                alt={resolveAltText(seriesItem.coverMedia, seriesItem.name)}
                width={1000}
                height={1000}
                aspect={1}
                tone="plum"
                sizes="(min-width: 1024px) 45vw, 100vw"
                priority
                className="h-auto w-full object-contain lg:h-full"
              />
            </div>
          </div>
        </div>
      </div>

      <div className={`container-editorial ${articles.length || hasDepth ? 'py-14' : 'py-10'}`}>
        {seriesItem.content?.length > 0 && (
          <div className="max-w-reading">
            <ArticleContent blocks={seriesItem.content} />
          </div>
        )}

        {featured && (
          <section aria-labelledby="series-start-here" className="mt-12 max-w-reading">
            <h2 id="series-start-here" className="font-serif text-2xl font-semibold text-charcoal">
              Start here
            </h2>
            <div className="mt-5">
              <ArticleCard article={featured} variant="horizontal" />
            </div>
          </section>
        )}

        <ProfilePreviewList id="series-people" heading="People in this series" items={seriesItem.people} basePath="/people" metaKey="title" />

        <div className={hasDepth ? 'mt-14' : ''}>
          {hasDepth && <h2 className="mb-6 font-serif text-2xl font-semibold text-charcoal">Stories in this series</h2>}
          {stories.length ? (
            <div className="grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
              {stories.map((a) => (
                <ArticleCard key={a.id} article={a} />
              ))}
            </div>
          ) : featured ? null : (
            <EmptyState title="No stories published yet" />
          )}
        </div>

        {seriesItem.sources?.length > 0 && (
          <div className="max-w-reading">
            <SourceReferences sources={seriesItem.sources} id="series-sources" />
          </div>
        )}
      </div>
    </div>
  )
}
