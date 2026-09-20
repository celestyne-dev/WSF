import { useParams } from 'react-router-dom'
import { Download, Lock } from 'lucide-react'
import { getResourceBySlug, resources } from '../mock/resources'
import { getAuthorBySlug } from '../mock/authors'
import { formatCurrency } from '../utils/format'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ResourceCard from '../components/cards/ResourceCard'
import NotFoundPage from './NotFoundPage'

export default function ResourceDetailPage() {
  const { slug } = useParams()
  const resource = getResourceBySlug(slug)
  if (!resource) return <NotFoundPage />

  const author = getAuthorBySlug(resource.authorSlug)
  const more = resources.filter((r) => r.slug !== slug && r.topicSlug === resource.topicSlug).slice(0, 3)

  useSeo({
    title: `${resource.name} | Women Shaping Futures Resources`,
    description: resource.description,
    canonical: `https://womenshapingfutures.org/resources/${resource.slug}`,
  })

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Resources', to: '/resources' }, { label: resource.name }]} />
      </div>
      <div className="container-editorial grid grid-cols-1 gap-10 py-10 sm:grid-cols-[320px_1fr]">
        <MediaImage mediaPath={resource.coverImage} alt={resource.name} width={800} height={560} aspect={10 / 7} className="w-full object-cover" />
        <div>
          <span className="eyebrow">{resource.type}</span>
          <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{resource.name}</h1>
          {author && <p className="mt-2 text-sm text-charcoal-600">By {author.name}</p>}
          <p className="mt-4 max-w-xl text-base leading-relaxed text-charcoal-600">{resource.description}</p>
          <p className="mt-4 font-serif text-2xl font-semibold text-charcoal">
            {resource.isPremium ? formatCurrency(resource.price, resource.currency) : 'Free'}
          </p>
          <button type="button" className="btn-primary mt-5 inline-flex">
            {resource.isPremium ? <Lock size={16} /> : <Download size={16} />}
            {resource.isPremium ? 'Unlock resource' : 'Download now'}
          </button>
        </div>
      </div>

      {more.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">You may also like</p>
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
            {more.map((r) => (
              <ResourceCard key={r.id} resource={r} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
