import { useParams } from 'react-router-dom'
import { getSeriesBySlug } from '../mock/series'
import { getArticlesBySeries } from '../mock/articles'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import CloudinaryImage from '../components/ui/CloudinaryImage'
import ArticleCard from '../components/cards/ArticleCard'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

export default function SeriesDetailPage() {
  const { slug } = useParams()
  const seriesItem = getSeriesBySlug(slug)
  if (!seriesItem) return <NotFoundPage />

  const articles = getArticlesBySeries(slug)

  useSeo({
    title: `${seriesItem.name} | Women Shaping Futures`,
    description: seriesItem.description,
    canonical: `https://womenshapingfutures.org/series/${seriesItem.slug}`,
  })

  return (
    <div>
      <div className="relative flex min-h-[320px] items-end bg-plum-700">
        <CloudinaryImage
          publicId={seriesItem.coverImage}
          alt={seriesItem.name}
          width={1920}
          height={640}
          aspect={3}
          tone="plum"
          priority
          className="absolute inset-0 h-full w-full object-cover opacity-60"
        />
        <div className="container-editorial relative py-10 text-ivory">
          <Breadcrumb items={[{ label: 'Series', to: '/series' }, { label: seriesItem.name }]} />
          <p className="eyebrow mt-4 !text-blush-200">Series</p>
          <h1 className="mt-2 font-serif text-4xl font-semibold sm:text-5xl">{seriesItem.name}</h1>
          <p className="mt-3 max-w-2xl text-ivory/85">{seriesItem.description}</p>
          {seriesItem.sponsor && <p className="mt-3 text-xs uppercase tracking-wide text-ivory/60">Presented in partnership with {seriesItem.sponsor.name}</p>}
        </div>
      </div>

      <div className="container-editorial py-14">
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
