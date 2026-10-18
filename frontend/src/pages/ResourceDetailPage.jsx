import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { Link, useLocation, useParams } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Download, Lock, Mail, ExternalLink, Sparkles, X } from 'lucide-react'
import { fetchResourceBySlug, fetchResources, requestResourceAccess, startResourceCheckout } from '../api/resources'
import { fetchMyCircleMembership } from '../api/circle'
import { getResourceCheckoutErrorPresentation } from '../utils/resourcePayment'
import { resolveImage, resolveAltText } from '../utils/media'
import { formatCurrency } from '../utils/format'
import { trackEvent, withAcquisitionMetadata } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ShareBar from '../components/ui/ShareBar'
import NewsletterForm from '../components/ui/NewsletterForm'
import SaveButton from '../components/account/SaveButton'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

// Valid schema.org structured data for a downloadable resource — built
// only from fields this record actually carries. @type checks
// resource.type === 'Video Resource' — the Resource model's actual
// content-type field (see RESOURCE_TYPES in app/models/resource.py) —
// never resource.accessType (the delivery/gating mechanism), which has
// no "video" value at all and was the wrong field checked here before
// this correction. Must match the server's _build_resource_json_ld
// exactly (app/services/spa_shell.py), or hydration overwrites the
// server's correct SSR @type with a wrong one.
function useResourceStructuredData(resource, canonicalUrl) {
  const siteName = useSelector((s) => s.site.settings?.site?.name) || 'Women Shaping Futures'
  useEffect(() => {
    if (!resource) return
    const data = {
      '@context': 'https://schema.org',
      '@type': resource.type === 'Video Resource' ? 'VideoObject' : 'DigitalDocument',
      name: resource.name,
      description: resource.shortDescription || resource.name,
      ...(resource.coverImage ? { image: resolveImage(resource.coverImage, { width: 1200, height: 630 }) } : {}),
      url: canonicalUrl,
      ...(resource.author?.name
        ? { author: { '@type': 'Person', name: resource.author.name } }
        : resource.authorName
          ? { author: { '@type': 'Organization', name: resource.authorName } }
          : {}),
      publisher: { '@type': 'Organization', name: siteName },
    }
    // A zero-price Offer is only truthful for a resource that's openly
    // available for the taking. member_only/circle_only gate on
    // something real (an account, a paid Circle membership) rather than
    // a price, so neither is a zero-price Offer — omitted entirely
    // rather than falsely advertised as free/InStock. premium now has a
    // real, purchasable price (see app/services/resource_payments.py)
    // and gets its own real Offer instead of being omitted.
    if (['direct_download', 'email_gate', 'external_link'].includes(resource.accessType)) {
      data.offers = {
        '@type': 'Offer',
        price: 0,
        priceCurrency: resource.currency || 'KES',
        availability: 'https://schema.org/InStock',
      }
    } else if (resource.accessType === 'premium') {
      data.offers = {
        '@type': 'Offer',
        price: resource.price,
        priceCurrency: resource.currency || 'KES',
        availability: 'https://schema.org/InStock',
        url: canonicalUrl,
      }
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
  }, [resource, canonicalUrl, siteName])
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
          <button type="submit" disabled={submitting} aria-busy={submitting} className="btn-primary w-full !py-2.5 text-sm disabled:opacity-60">
            {submitting ? 'Preparing your download…' : 'Get the download'}
          </button>
        </form>
      </div>
    </div>
  )
}

// The one place a resource's access_type decides its CTA. Backend
// remains authoritative for the actual grant (POST /access) — this only
// decides which button/link to show, and never claims access the
// backend hasn't confirmed (see spec section J: "Backend remains
// authoritative... Show a safe fallback" if the Circle check fails).
function AccessCta({
  resource,
  accessToken,
  requesting,
  onAccessClick,
  onEmailGateClick,
  checkingOut,
  checkoutError,
  onCheckoutClick,
  circleMembership,
}) {
  const location = useLocation()

  if (resource.accessType === 'premium') {
    const priceLabel = formatCurrency(resource.price, resource.currency)
    const returnTo = `/resources/${resource.slug}`

    // Shown under the Buy CTA for a purchaser candidate only — never
    // once she already holds access via purchase or Circle (see the
    // viewerCanAccess branch below, which never renders this).
    // Restrained, informational, and deliberately never styled as a
    // second purchase action (no button, no price repeated) — see spec
    // section 5. Purely presentational: no entitlement/business rule is
    // read or changed here.
    const membershipNote = (
      <p className="mt-3 max-w-sm text-xs leading-relaxed text-charcoal-600/80">
        WSF Circle members get access to Premium Resources as part of an active membership.{' '}
        <Link to="/circle" className="font-semibold text-burgundy-600 hover:underline">
          WSF Circle
        </Link>
      </p>
    )

    if (!accessToken) {
      return (
        <div className="mt-5">
          <Link to="/register" state={{ from: returnTo }} className="btn-primary inline-flex">
            <Lock size={16} /> Buy for {priceLabel}
          </Link>
          <p className="mt-2.5 text-sm text-charcoal-600">
            Already have a WSF account?{' '}
            <Link to="/login" state={{ from: returnTo }} className="font-semibold text-burgundy-600 hover:underline">
              Sign in
            </Link>
          </p>
          <p className="mt-2.5 max-w-sm text-xs text-charcoal-600/70">
            A free WSF account is required so your purchase and downloads stay linked to you.
          </p>
          {membershipNote}
        </div>
      )
    }

    if (resource.viewerCanAccess === true) {
      // "purchase" takes precedence when a viewer somehow holds both
      // (see backend/app/services/resource_access.py's
      // get_viewer_access_source) — the durable entitlement is the one
      // worth naming. Circle-included access is never labeled
      // "Purchased": nothing was bought, so nothing should say so.
      const label = resource.viewerAccessSource === 'circle' ? 'Included with WSF Circle' : 'Purchased'
      return (
        <div className="mt-5">
          <p className="mb-2 inline-flex items-center gap-1.5 text-sm font-semibold text-burgundy-600">
            <Lock size={14} /> {label}
          </p>
          <button type="button" onClick={onAccessClick} disabled={requesting} aria-busy={requesting} className="btn-primary inline-flex disabled:opacity-60">
            <Download size={16} /> {requesting ? 'Preparing…' : 'Download resource'}
          </button>
        </div>
      )
    }

    return (
      <div className="mt-5">
        <button type="button" onClick={onCheckoutClick} disabled={checkingOut} aria-busy={checkingOut} className="btn-primary inline-flex disabled:opacity-60">
          <Lock size={16} /> {checkingOut ? 'Starting secure checkout…' : `Buy securely — ${priceLabel}`}
        </button>
        {checkoutError && <p className="mt-2 text-sm text-burgundy-600">{checkoutError}</p>}
        {membershipNote}
      </div>
    )
  }

  if (resource.accessType === 'member_only') {
    if (!accessToken) {
      return (
        <Link to="/login" state={{ from: location.pathname }} className="btn-primary mt-5 inline-flex">
          <Lock size={16} /> Sign in to access
        </Link>
      )
    }
    return (
      <button type="button" onClick={onAccessClick} disabled={requesting} aria-busy={requesting} className="btn-primary mt-5 inline-flex disabled:opacity-60">
        <Download size={16} /> {requesting ? 'Preparing…' : 'Access resource'}
      </button>
    )
  }

  if (resource.accessType === 'circle_only') {
    if (!accessToken) {
      return (
        <Link to="/login" state={{ from: location.pathname }} className="btn-primary mt-5 inline-flex">
          <Lock size={16} /> Sign in
        </Link>
      )
    }
    if (circleMembership === undefined) {
      return (
        <button type="button" disabled aria-busy="true" className="btn-secondary mt-5 inline-flex opacity-60">
          Checking membership…
        </button>
      )
    }
    if (!circleMembership?.hasAccess) {
      return (
        <Link to="/circle" className="btn-primary mt-5 inline-flex">
          Explore WSF Circle
        </Link>
      )
    }
    // A yearly-only (annual-member bonus) Resource: a monthly member
    // passes the ordinary Circle check above but not this narrower tier
    // (see backend/app/services/resource_access.py's
    // yearly_circle_required) — never show a working Download for her,
    // never pretend she's purchased anything, never send her to Paystack
    // for a Resource purchase. WSF Circle's own plan page is the only
    // legitimate next step, same discovery path a non-member already sees
    // just above.
    if (resource.circleAccessLevel === 'yearly_members' && circleMembership.subscription?.plan?.billingInterval !== 'yearly') {
      return (
        <Link to="/circle" className="btn-secondary mt-5 inline-flex">
          Explore WSF Circle Yearly
        </Link>
      )
    }
    return (
      <button type="button" onClick={onAccessClick} disabled={requesting} aria-busy={requesting} className="btn-primary mt-5 inline-flex disabled:opacity-60">
        <Download size={16} /> {requesting ? 'Preparing…' : 'Access resource'}
      </button>
    )
  }

  if (resource.accessType === 'email_gate') {
    return (
      <button type="button" onClick={onEmailGateClick} className="btn-primary mt-5 inline-flex">
        <Mail size={16} /> Get the free download
      </button>
    )
  }

  const Icon = resource.accessType === 'external_link' ? ExternalLink : Download
  const label = resource.accessType === 'external_link' ? 'Visit resource' : 'Download now'
  return (
    <button type="button" onClick={onAccessClick} disabled={requesting} aria-busy={requesting} className="btn-primary mt-5 inline-flex disabled:opacity-60">
      <Icon size={16} /> {requesting ? 'Preparing…' : label}
    </button>
  )
}

// One cohesive preview area for the hero's left column: the cover plus
// (when a gallery exists) a redesigned thumbnail strip beneath it.
// Selecting a thumbnail swaps which image the large frame shows — a
// purely local display preference, never a fetch or an access check:
// every image here already came back on the SAME public resource
// payload (resource.coverMedia / resource.images), nothing protected,
// and no new API call is made. Resources with no gallery render exactly
// as before — just the cover, no strip.
function ResourceGallery({ resource }) {
  const [selected, setSelected] = useState(0)
  const hasGallery = resource.images?.length > 0
  const frames = hasGallery
    ? [{ media: resource.coverMedia, mediaPath: resource.coverImage }, ...resource.images.map((img) => ({ media: img.media }))]
    : null
  const active = frames ? frames[selected] || frames[0] : null

  return (
    <div>
      <div className="overflow-hidden border border-taupe-200 shadow-card">
        <MediaImage
          media={active ? active.media : resource.coverMedia}
          mediaPath={active ? active.mediaPath : resource.coverImage}
          variant="medium"
          alt={resolveAltText(active ? active.media : resource.coverMedia, resource.name)}
          width={800}
          height={1000}
          aspect={4 / 5}
          sizes="(min-width: 640px) 360px, 100vw"
          className="w-full object-cover"
          priority
        />
      </div>

      {hasGallery && (
        <div className="mt-4">
          <span className="eyebrow">Preview inside</span>
          <p className="mt-1 text-xs text-charcoal-600/70">Explore a few sample pages.</p>
          <div className="mt-3 flex gap-2 overflow-x-auto scrollbar-none pb-1">
            {frames.map((frame, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setSelected(i)}
                aria-pressed={selected === i}
                aria-label={i === 0 ? 'Show cover image' : `Show preview page ${i}`}
                className={`shrink-0 overflow-hidden border-2 transition-all ${
                  selected === i
                    ? 'border-plum-600 ring-2 ring-plum-600/30 ring-offset-2 ring-offset-ivory'
                    : 'border-transparent hover:border-taupe-300'
                }`}
              >
                <MediaImage
                  media={frame.media}
                  mediaPath={frame.mediaPath}
                  variant="thumbnail"
                  alt={frame.media?.altText || (i === 0 ? `${resource.name} cover` : `${resource.name} preview ${i}`)}
                  width={80}
                  height={100}
                  aspect={4 / 5}
                  className="h-[100px] w-20 object-cover"
                />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function getResourceAccessBadge(resource) {
  const isYearlyOnly = resource.accessType === 'circle_only' && resource.circleAccessLevel === 'yearly_members'
  if (isYearlyOnly) return { Icon: Sparkles, label: 'WSF Circle Yearly' }
  const badges = {
    email_gate: { Icon: Mail, label: 'Email required' },
    member_only: { Icon: Lock, label: 'WSF account' },
    circle_only: { Icon: Sparkles, label: 'WSF Circle' },
    premium: { Icon: Lock, label: 'Premium' },
    external_link: { Icon: ExternalLink, label: 'External' },
  }
  return badges[resource.accessType]
}

function getResourcePriceLabel(resource) {
  return resource.accessType === 'circle_only' ? 'WSF Circle' : resource.isFree ? 'Free' : formatCurrency(resource.price, resource.currency)
}

// A Resource-detail-specific recommendation card for the 2/3-up related
// grid — smaller image footprint, text sooner — kept local here rather
// than changed on the shared ResourceCard, which also drives the denser
// ResourcesPage grid where a taller cover is the right call.
function RelatedResourceCard({ resource }) {
  const badge = getResourceAccessBadge(resource)
  return (
    <Link to={`/resources/${resource.slug}`} className="group block">
      <div className="relative overflow-hidden bg-taupe-100">
        <MediaImage
          media={resource.coverMedia}
          variant="card"
          mediaPath={resource.coverImage}
          alt={resolveAltText(resource.coverMedia, resource.name)}
          width={640}
          height={480}
          aspect={4 / 3}
          sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
          className="aspect-[4/3] w-full object-cover transition-transform duration-250 group-hover:scale-105"
        />
        {resource.featured && (
          <span className="absolute left-3 top-3 bg-burgundy-600 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>
        )}
        {badge && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1 bg-charcoal/85 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-ivory">
            <badge.Icon size={11} /> {badge.label}
          </span>
        )}
      </div>
      <div className="mt-3">
        <span className="eyebrow">{resource.type}</span>
        <h3 className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {resource.name}
        </h3>
        {resource.shortDescription && <p className="mt-1 line-clamp-2 text-sm text-charcoal-600/80">{resource.shortDescription}</p>}
        <p className="mt-1.5 text-sm font-medium text-charcoal-600">{getResourcePriceLabel(resource)}</p>
      </div>
    </Link>
  )
}

// The wide treatment for the one-related-result case — the vertical
// ResourceCard shape left a single card stranded at the far left with
// the rest of the row empty; this fills that same footprint on purpose
// instead, without stretching the portrait cover out of proportion.
function RelatedResourceWideCard({ resource }) {
  const badge = getResourceAccessBadge(resource)
  return (
    <Link
      to={`/resources/${resource.slug}`}
      className="group flex max-w-[720px] flex-col overflow-hidden border border-taupe-200 transition-colors hover:border-burgundy-300 sm:flex-row"
    >
      <div className="relative shrink-0 overflow-hidden bg-taupe-100 sm:w-48">
        <MediaImage
          media={resource.coverMedia}
          variant="card"
          mediaPath={resource.coverImage}
          alt={resolveAltText(resource.coverMedia, resource.name)}
          width={400}
          height={500}
          aspect={4 / 5}
          sizes="(min-width: 640px) 192px, 100vw"
          className="aspect-[4/5] w-full object-cover transition-transform duration-250 group-hover:scale-105 sm:h-full"
        />
        {resource.featured && (
          <span className="absolute left-3 top-3 bg-burgundy-600 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>
        )}
      </div>
      <div className="flex flex-1 flex-col justify-center p-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow">{resource.type}</span>
          {badge && (
            <span className="inline-flex items-center gap-1 bg-charcoal/85 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-ivory">
              <badge.Icon size={11} /> {badge.label}
            </span>
          )}
        </div>
        <h3 className="mt-2 font-serif text-xl font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {resource.name}
        </h3>
        {resource.shortDescription && (
          <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-charcoal-600/80">{resource.shortDescription}</p>
        )}
        <p className="mt-3 text-sm font-semibold text-charcoal-600">{getResourcePriceLabel(resource)}</p>
      </div>
    </Link>
  )
}

export default function ResourceDetailPage() {
  const { slug } = useParams()
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [resource, setResource] = useState(undefined)
  const [related, setRelated] = useState([])
  const [error, setError] = useState(null)
  const [showEmailGate, setShowEmailGate] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [checkingOut, setCheckingOut] = useState(false)
  const [checkoutError, setCheckoutError] = useState(null)
  const [circleMembership, setCircleMembership] = useState(undefined)

  useEffect(() => {
    if (!accessToken || resource?.accessType !== 'circle_only') return undefined
    let active = true
    fetchMyCircleMembership()
      .then((result) => active && setCircleMembership(result))
      .catch(() => active && setCircleMembership(null))
    return () => {
      active = false
    }
  }, [accessToken, resource?.accessType, resource?.slug])

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
  useBreadcrumbStructuredData(resource ? [{ label: 'Resources', to: '/resources' }, { label: resource.name }] : null, canonicalUrl)

  async function openUrl(url) {
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  async function handleAccessClick() {
    if (!resource) return

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

  // A background refresh for the two stale-state checkout recoveries
  // below — deliberately narrow: only `resource` is reloaded (so
  // viewerCanAccess/viewerAccessSource catch up and the normal render
  // takes over), never `related`/`error`/`showEmailGate`, which belong
  // only to the full page-load effect above. Failures are swallowed —
  // worst case the page simply keeps showing its last-known state,
  // which is no worse than before this recovery ran.
  async function refetchResourceForAccessRecovery() {
    try {
      const data = await fetchResourceBySlug(slug)
      if (data) setResource(data)
    } catch {
      // Intentionally silent — see comment above.
    }
  }

  // Starts a hosted Paystack checkout for a premium Resource purchase —
  // see spec section F/G: never embeds a card form, never sends
  // price/currency/user/email, and never infers success from the
  // redirect itself (POST /resources/payments/<reference> on the
  // callback page remains the sole authority for that).
  async function handlePremiumCheckout() {
    if (!resource || checkingOut) return
    setCheckoutError(null)
    setCheckingOut(true)
    trackEvent('resource_checkout_click', { resourceSlug: resource.slug })
    try {
      const { authorizationUrl } = await startResourceCheckout(resource.slug)
      if (!authorizationUrl) throw new Error('Checkout response was missing an authorization URL.')
      trackEvent('resource_checkout_initialized', { resourceSlug: resource.slug })
      // Full browser redirect to Paystack's hosted checkout — never an
      // iframe, never a WSF-collected card/mobile-money form.
      window.location.assign(authorizationUrl)
    } catch (err) {
      const code = err?.response?.data?.error?.code
      if (code === 'already_purchased') {
        // The page's viewerCanAccess hint was stale (e.g. purchased in
        // another tab) — re-evaluate access directly instead of
        // showing a failure; backend entitlement remains authoritative
        // either way.
        setCheckingOut(false)
        handleAccessClick()
        return
      }
      if (code === 'included_with_circle') {
        // The viewer gained active WSF Circle access since this page
        // loaded (stale page, duplicate tab, membership activated
        // mid-session) — never a payment failure, never a Paystack
        // retry. Refetch so the CTA becomes "Included with WSF Circle /
        // Download resource" on its own; the backend already charged
        // nothing and created nothing.
        setCheckingOut(false)
        refetchResourceForAccessRecovery()
        return
      }
      setCheckoutError(getResourceCheckoutErrorPresentation(code))
      setCheckingOut(false)
    }
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this resource" description={error} /></div>
  if (resource === undefined) return <PageLoader />
  if (resource === null) return <NotFoundPage />

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Resources', to: '/resources' }, { label: resource.name }]} />
      </div>
      <div className="container-editorial grid grid-cols-1 gap-10 py-10 sm:grid-cols-[360px_1fr] lg:gap-14">
        <div>
          <ResourceGallery resource={resource} key={resource.slug} />
        </div>
        <div>
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="eyebrow">{resource.type}</span>
              {resource.featured && <span className="bg-burgundy-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>}
            </div>
            <SaveButton contentType="resource" contentId={resource.id} />
          </div>
          <h1 className="mt-3 max-w-xl font-serif text-4xl font-semibold leading-tight text-charcoal sm:text-5xl">{resource.name}</h1>
          {resource.subtitle && <p className="mt-3 max-w-xl text-lg leading-relaxed text-charcoal-600">{resource.subtitle}</p>}
          {(resource.author?.name || resource.authorName) && (
            <p className="mt-4 text-sm font-medium text-charcoal-600">By {resource.author?.name || resource.authorName}</p>
          )}

          {resource.sponsored && (
            <div className="mt-4 inline-flex items-center gap-2 border border-dashed border-taupe-300 bg-blush-50 px-4 py-2 text-xs text-charcoal-600">
              <span className="font-semibold uppercase tracking-wide text-burgundy-600">Sponsored</span>
              <span>This resource is a paid placement{resource.sponsor?.name ? ` from ${resource.sponsor.name}` : ''}.</span>
            </div>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-charcoal-600/70">
            {resource.fileFormat && <span>{resource.fileFormat}</span>}
            {resource.fileFormat && resource.pageCount && <span aria-hidden="true">&middot;</span>}
            {resource.pageCount && <span>{resource.pageCount} pages</span>}
          </div>

          {(() => {
            const isYearlyOnly = resource.accessType === 'circle_only' && resource.circleAccessLevel === 'yearly_members'
            // Only an active member of the Circle Yearly plan actually
            // holds this narrower tier — a monthly member sees this as
            // "available", not "included", even though she does pass the
            // ordinary circle_only check (see AccessCta's own circle_only
            // branch for the matching CTA treatment).
            const monthlyMemberOnYearlyOnly =
              isYearlyOnly && circleMembership?.hasAccess && circleMembership?.subscription?.plan?.billingInterval !== 'yearly'
            return (
              <>
                <p className="mt-5 font-serif text-3xl font-semibold text-charcoal">
                  {resource.accessType === 'circle_only'
                    ? isYearlyOnly
                      ? monthlyMemberOnYearlyOnly
                        ? 'Available with WSF Circle Yearly'
                        : 'Included with WSF Circle Yearly'
                      : 'Included with WSF Circle'
                    : resource.isFree
                      ? 'Free'
                      : formatCurrency(resource.price, resource.currency)}
                </p>
                {monthlyMemberOnYearlyOnly && (
                  <p className="mt-1 text-xs text-charcoal-600/70">
                    This annual-member bonus is included with WSF Circle Yearly.
                  </p>
                )}
              </>
            )
          })()}
          {resource.accessType === 'premium' && resource.viewerCanAccess !== true && (
            <p className="mt-1.5 text-xs text-charcoal-600/70">Included with an active WSF Circle membership.</p>
          )}

          <AccessCta
            resource={resource}
            accessToken={accessToken}
            requesting={requesting}
            circleMembership={circleMembership}
            onAccessClick={handleAccessClick}
            onEmailGateClick={() => setShowEmailGate(true)}
            checkingOut={checkingOut}
            checkoutError={checkoutError}
            onCheckoutClick={handlePremiumCheckout}
          />

          <div className="mt-8 flex items-center gap-3 border-t border-taupe-200 pt-5">
            <span className="text-xs font-medium uppercase tracking-wide text-charcoal-600/50">Share</span>
            <div className="origin-left scale-90 opacity-80">
              <ShareBar title={resource.name} url={canonicalUrl} trackEventName="resource_share_click" trackPayload={{ resourceSlug: resource.slug }} />
            </div>
          </div>
        </div>
      </div>

      <div className="container-editorial pb-4 pt-2">
        <div className="max-w-[1150px] [&_h2]:max-w-[760px] [&_h3]:max-w-[760px] [&_h4]:max-w-[760px] [&_p]:max-w-[760px]">
          <ArticleContent blocks={resource.description} variant="resource" />
        </div>
      </div>

      {related.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-16">
          <div className="max-w-[1160px]">
            <span className="eyebrow">Related resources</span>
            <h2 className="mt-2 font-serif text-2xl font-semibold text-charcoal sm:text-3xl">You may also like</h2>
            {related.length === 1 ? (
              <div className="mt-8">
                <RelatedResourceWideCard resource={related[0]} />
              </div>
            ) : (
              <div className={`mt-8 grid grid-cols-1 gap-8 ${related.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-2 lg:grid-cols-3'}`}>
                {related.map((r) => (
                  <div key={r.id} className={related.length === 2 ? 'max-w-sm' : undefined}>
                    <RelatedResourceCard resource={r} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <section className="border-t border-taupe-200 bg-charcoal py-16 text-ivory">
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
