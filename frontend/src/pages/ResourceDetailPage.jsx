import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Download, Lock, Mail, ExternalLink, X } from 'lucide-react'
import { fetchResourceBySlug, fetchResources, requestResourceAccess } from '../api/resources'
import { resolveImage } from '../utils/media'
import { formatCurrency } from '../utils/format'
import { trackEvent, withAcquisitionMetadata } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ShareBar from '../components/ui/ShareBar'
import NewsletterForm from '../components/ui/NewsletterForm'
import ResourceCard from '../components/cards/ResourceCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

// Valid schema.org structured data for a downloadable resource — built
// only from fields this record actually carries.
function useResourceStructuredData(resource, canonicalUrl) {
  useEffect(() => {
    if (!resource) return
    const data = {
      '@context': 'https://schema.org',
      '@type': resource.accessType === 'video_resource' ? 'VideoObject' : 'DigitalDocument',
      name: resource.name,
      description: resource.shortDescription || resource.name,
      ...(resource.coverImage ? { image: resolveImage(resource.coverImage, { width: 1200, height: 630 }) } : {}),
      url: canonicalUrl,
      ...(resource.author?.name
        ? { author: { '@type': 'Person', name: resource.author.name } }
        : resource.authorName
          ? { author: { '@type': 'Organization', name: resource.authorName } }
          : {}),
      publisher: { '@type': 'Organization', name: 'Women Shaping Futures' },
      offers: {
        '@type': 'Offer',
        price: resource.isFree ? 0 : resource.price,
        priceCurrency: resource.currency || 'USD',
        availability: 'https://schema.org/InStock',
      },
    }
    let el = document.head.querySelector('script[data-resource-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-resource-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [resource, canonicalUrl])
}

function EmailGateModal({ resource, onClose, onSuccess }) {
  const [firstName, setFirstName] = useState('')
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email.includes('@')) {
      toast.error('Please enter a valid email address.')
      return
    }
    setSubmitting(true)
    try {
      const { url } = await requestResourceAccess(
        resource.slug,
        withAcquisitionMetadata({ email, firstName, newsletterConsent: consent }),
      )
      trackEvent('resource_download_success', { resourceSlug: resource.slug, accessType: resource.accessType })
      onSuccess(url)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal-800/60 p-4">
      <div className="relative w-full max-w-md bg-white p-6 sm:p-8">
        <button type="button" onClick={onClose} aria-label="Close" className="absolute right-4 top-4 text-charcoal-600 hover:text-burgundy-600">
          <X size={18} />
        </button>
        <span className="eyebrow">Free download</span>
        <h2 className="mt-2 font-serif text-xl font-semibold text-charcoal">{resource.name}</h2>
        <p className="mt-2 text-sm text-charcoal-600">Enter your details and we'll send you straight to the download.</p>
        <form onSubmit={handleSubmit} className="mt-5 space-y-3">
          <div>
            <label htmlFor="resource-first-name" className="sr-only">First name</label>
            <input
              id="resource-first-name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="First name (optional)"
              className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="resource-email" className="sr-only">Email address</label>
            <input
              id="resource-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Your email address"
              className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </div>
          <label className="flex items-start gap-2 text-xs text-charcoal-600">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5" />
            Also subscribe me to the Women Shaping Futures newsletter.
          </label>
          <button type="submit" disabled={submitting} className="btn-primary w-full !py-2.5 text-sm disabled:opacity-60">
            {submitting ? 'Preparing your download…' : 'Get the download'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function ResourceDetailPage() {
  const { slug } = useParams()
  const [resource, setResource] = useState(undefined)
  const [related, setRelated] = useState([])
  const [error, setError] = useState(null)
  const [showEmailGate, setShowEmailGate] = useState(false)
  const [requesting, setRequesting] = useState(false)

  useEffect(() => {
    let active = true
    setResource(undefined)
    setRelated([])
    setError(null)
    setShowEmailGate(false)

    fetchResourceBySlug(slug)
      .then((data) => {
        if (!active) return
        setResource(data)
        if (!data) return

        trackEvent('resource_view', { resourceSlug: data.slug, accessType: data.accessType })

        const topicSlug = data.topicSlugs?.[0]
        if (topicSlug) {
          fetchResources({ topic: topicSlug, pageSize: 4 })
            .then((res) => active && setRelated(res.items.filter((r) => r.slug !== slug).slice(0, 3)))
            .catch(() => {})
        }
      })
      .catch(() => active && setError('Something went wrong loading this resource. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = resource ? `https://womenshapingfutures.org/resources/${resource.slug}` : ''

  useSeo(
    resource
      ? {
          title: resource.seo?.title || `${resource.name} | Women Shaping Futures Resources`,
          description: resource.seo?.description || resource.shortDescription || resource.name,
          canonical: resource.seo?.canonical || canonicalUrl,
          image: resource.coverImage ? resolveImage(resource.coverImage, { width: 1200, height: 630 }) : undefined,
        }
      : {},
  )

  useResourceStructuredData(resource, canonicalUrl)

  async function openUrl(url) {
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  async function handleAccessClick() {
    if (!resource) return

    if (resource.accessType === 'premium') {
      trackEvent('resource_premium_cta_click', { resourceSlug: resource.slug })
      toast('Purchasing isn\'t available yet — check back soon.')
      return
    }
    if (resource.accessType === 'member_only') {
      trackEvent('resource_premium_cta_click', { resourceSlug: resource.slug })
      toast('An account is required for this resource — accounts aren\'t available yet.')
      return
    }
    if (resource.accessType === 'email_gate') {
      setShowEmailGate(true)
      return
    }

    trackEvent(resource.accessType === 'external_link' ? 'resource_external_click' : 'resource_download_click', {
      resourceSlug: resource.slug,
    })
    setRequesting(true)
    try {
      const { url } = await requestResourceAccess(resource.slug)
      trackEvent('resource_download_success', { resourceSlug: resource.slug, accessType: resource.accessType })
      openUrl(url)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setRequesting(false)
    }
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this resource" description={error} /></div>
  if (resource === undefined) return <PageLoader />
  if (resource === null) return <NotFoundPage />

  const ButtonIcon = resource.accessType === 'external_link' ? ExternalLink : resource.accessType === 'email_gate' ? Mail : resource.accessType === 'premium' || resource.accessType === 'member_only' ? Lock : Download
  const buttonLabel =
    resource.accessType === 'external_link' ? 'Visit resource'
      : resource.accessType === 'premium' ? `Unlock — ${formatCurrency(resource.price, resource.currency)}`
      : resource.accessType === 'member_only' ? 'Sign in required'
      : resource.accessType === 'email_gate' ? 'Get the free download'
      : 'Download now'

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Resources', to: '/resources' }, { label: resource.name }]} />
      </div>
      <div className="container-editorial grid grid-cols-1 gap-10 py-10 sm:grid-cols-[360px_1fr]">
        <div>
          <MediaImage media={resource.coverMedia} variant="medium" mediaPath={resource.coverImage} alt={resource.name} width={800} height={1000} aspect={4 / 5} className="w-full object-cover" />
          {resource.images?.length > 0 && (
            <div className="mt-3 grid grid-cols-3 gap-2">
              {resource.images.map((img, i) => (
                <MediaImage key={img.id ?? i} media={img.media} variant="thumbnail" width={200} height={200} aspect={1} className="w-full object-cover" />
              ))}
            </div>
          )}
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="eyebrow">{resource.type}</span>
            {resource.featured && <span className="bg-burgundy-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>}
          </div>
          <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{resource.name}</h1>
          {resource.subtitle && <p className="mt-2 max-w-xl text-lg text-charcoal-600">{resource.subtitle}</p>}
          {(resource.author?.name || resource.authorName) && (
            <p className="mt-3 text-sm text-charcoal-600">By {resource.author?.name || resource.authorName}</p>
          )}

          {resource.sponsored && (
            <div className="mt-4 inline-flex items-center gap-2 border border-dashed border-taupe-300 bg-blush-50 px-4 py-2 text-xs text-charcoal-600">
              <span className="font-semibold uppercase tracking-wide text-burgundy-600">Sponsored</span>
              <span>This resource is a paid placement{resource.sponsor?.name ? ` from ${resource.sponsor.name}` : ''}.</span>
            </div>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-charcoal-600/70">
            {resource.fileFormat && <span>{resource.fileFormat}</span>}
            {resource.pageCount && <span>{resource.pageCount} pages</span>}
          </div>

          <p className="mt-4 font-serif text-2xl font-semibold text-charcoal">
            {resource.isFree ? 'Free' : formatCurrency(resource.price, resource.currency)}
          </p>

          <button type="button" onClick={handleAccessClick} disabled={requesting} className="btn-primary mt-5 inline-flex disabled:opacity-60">
            <ButtonIcon size={16} />
            {requesting ? 'Preparing…' : buttonLabel}
          </button>

          <div className="mt-6">
            <ShareBar title={resource.name} url={canonicalUrl} trackEventName="resource_share_click" trackPayload={{ resourceSlug: resource.slug }} />
          </div>
        </div>
      </div>

      <div className="container-editorial max-w-reading pb-4">
        <ArticleContent blocks={resource.description} />
      </div>

      {related.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">You may also like</p>
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
            {related.map((r) => (
              <ResourceCard key={r.id} resource={r} />
            ))}
          </div>
        </div>
      )}

      <section className="border-t border-taupe-200 bg-charcoal py-14 text-ivory">
        <div className="container-editorial flex flex-col items-center text-center">
          <p className="eyebrow !text-blush-200">Never miss a new resource</p>
          <h2 className="mt-3 max-w-xl font-serif text-2xl font-semibold sm:text-3xl">Get new guides and toolkits in your inbox</h2>
          <div className="mt-6">
            <NewsletterForm variant="dark" source="resource_detail" />
          </div>
        </div>
      </section>

      {showEmailGate && (
        <EmailGateModal
          resource={resource}
          onClose={() => setShowEmailGate(false)}
          onSuccess={(url) => {
            setShowEmailGate(false)
            toast.success('Thanks! Your download is ready.')
            openUrl(url)
          }}
        />
      )}
    </div>
  )
}
