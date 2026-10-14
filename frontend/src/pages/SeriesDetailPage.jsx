import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchSeriesBySlug } from '../api/taxonomies'
import { fetchArticles } from '../api/articles'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleCard from '../components/cards/ArticleCard'
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
          title: `${seriesItem.name} | Women Shaping Futures`,
          description: seriesItem.description,
          canonical: `https://womenshapingfutures.org/series/${seriesItem.slug}`,
        }
      : {},
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this series" description={error} /></div>
  if (seriesItem === undefined) return <PageLoader />
  if (seriesItem === null) return <NotFoundPage />

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
                alt={seriesItem.name}
                width={1000}
                height={1000}
                aspect={1}
                tone="plum"
                priority
                className="h-auto w-full object-contain lg:h-full"
              />
            </div>
          </div>
        </div>
      </div>

      <div className={`container-editorial ${articles.length ? 'py-14' : 'py-10'}`}>
        {articles.length ? (
          <div className="grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {articles.map((a) => (
              <ArticleCard key={a.id} article={a} />
            ))}
          </div>
        ) : (
          <EmptyState title="No stories published yet" />
        )}
      </div>
    </div>
  )
}
