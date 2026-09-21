import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Download, Lock } from 'lucide-react'
import { fetchResourceBySlug, fetchResources } from '../api/resources'
import { fetchAuthorBySlug } from '../api/taxonomies'
import { formatCurrency } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ResourceCard from '../components/cards/ResourceCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

export default function ResourceDetailPage() {
  const { slug } = useParams()
  const [resource, setResource] = useState(undefined)
  const [author, setAuthor] = useState(null)
  const [more, setMore] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setResource(undefined)
    setAuthor(null)
    setMore([])
    setError(null)

    fetchResourceBySlug(slug)
      .then((data) => {
        if (!active) return
        setResource(data)
        if (!data) return

        if (data.authorSlug) {
          fetchAuthorBySlug(data.authorSlug)
            .then((a) => active && setAuthor(a))
            .catch(() => {})
        }

        if (data.topicSlug) {
          fetchResources({ topic: data.topicSlug, pageSize: 4 })
            .then((res) => active && setMore(res.items.filter((r) => r.slug !== slug).slice(0, 3)))
            .catch(() => {})
        }
      })
      .catch(() => active && setError('Something went wrong loading this resource. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  useSeo(
    resource
      ? {
          title: `${resource.name} | Women Shaping Futures Resources`,
          description: resource.description,
          canonical: `https://womenshapingfutures.org/resources/${resource.slug}`,
        }
      : {},
  )

  function handleDownloadClick() {
    trackEvent('resource_download_click', { resourceSlug: resource.slug, isPremium: resource.isPremium })
    toast.success(resource.isPremium ? 'Redirecting to checkout…' : 'Your download will begin shortly.')
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this resource" description={error} /></div>
  if (resource === undefined) return <PageLoader />
  if (resource === null) return <NotFoundPage />

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
          <button type="button" onClick={handleDownloadClick} className="btn-primary mt-5 inline-flex">
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
