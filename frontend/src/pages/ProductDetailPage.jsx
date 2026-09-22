import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ShoppingBag, Clock } from 'lucide-react'
import { fetchProductBySlug, fetchProducts } from '../api/products'
import { formatProductPrice, formatDiscountPercent } from '../utils/format'
import { resolveImage } from '../utils/media'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ProductCard from '../components/cards/ProductCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

const AVAILABILITY_SCHEMA = {
  available: 'https://schema.org/InStock',
  unavailable: 'https://schema.org/OutOfStock',
}

// Valid schema.org Product structured data — built only from fields this
// product record actually carries. Never fabricates reviews, ratings, or a
// discount; an Offer is only included when there's a real price to show.
function useProductStructuredData(product, canonicalUrl) {
  useEffect(() => {
    if (!product) return
    const data = {
      '@context': 'https://schema.org',
      '@type': 'Product',
      name: product.name,
      description: product.shortDescription || product.name,
      ...(product.coverImage ? { image: resolveImage(product.coverImage, { width: 1200, height: 1200 }) } : {}),
      ...(product.sku ? { sku: product.sku } : {}),
      ...(product.category?.name ? { category: product.category.name } : {}),
      url: canonicalUrl,
      ...(product.priceVisible
        ? {
            offers: {
              '@type': 'Offer',
              url: product.purchaseUrl || canonicalUrl,
              price: product.salePrice ?? product.price,
              priceCurrency: product.currency || 'USD',
              availability: product.isAvailable ? AVAILABILITY_SCHEMA.available : AVAILABILITY_SCHEMA.unavailable,
            },
          }
        : {}),
    }
    let el = document.head.querySelector('script[data-product-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-product-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [product, canonicalUrl])
}

export default function ProductDetailPage() {
  const { slug } = useParams()
  const [product, setProduct] = useState(undefined)
  const [more, setMore] = useState([])
  const [activeImage, setActiveImage] = useState(0)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setProduct(undefined)
    setMore([])
    setActiveImage(0)
    setError(null)

    fetchProductBySlug(slug)
      .then((data) => {
        if (!active) return
        setProduct(data)
        if (!data) return
        trackEvent('product_view', { productSlug: data.slug })

        if (data.category?.slug) {
          fetchProducts({ category: data.category.slug, pageSize: 4 })
            .then((res) => active && setMore(res.items.filter((p) => p.slug !== slug).slice(0, 3)))
            .catch(() => {})
        }
      })
      .catch(() => active && setError('Something went wrong loading this product. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = `https://womenshapingfutures.org/shop/${slug}`

  useSeo(
    product
      ? {
          title: product.seo?.title || `${product.name} | Women Shaping Futures Shop`,
          description: product.seo?.description || product.shortDescription,
          canonical: product.seo?.canonical || canonicalUrl,
          image: product.coverImage ? resolveImage(product.coverImage, { width: 1200, height: 1200 }) : undefined,
          robots: product.seo?.robots,
        }
      : {},
  )

  useProductStructuredData(product, canonicalUrl)

  function handleCtaClick() {
    trackEvent('product_cta_click', { productSlug: product.slug })
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this product" description={error} /></div>
  if (product === undefined) return <PageLoader />
  if (product === null) return <NotFoundPage />

  const gallery = [{ media: product.coverMedia, image: product.coverImage }, ...product.images.map((img) => ({ media: img.media, image: null }))].filter(
    (entry) => entry.media || entry.image,
  )
  const onSale = product.salePrice != null && product.salePrice < product.price
  const discountPercent = onSale ? formatDiscountPercent(product.price, product.salePrice) : null
  const canBuy = product.isAvailable && Boolean(product.purchaseUrl)

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Shop', to: '/shop' }, { label: product.name }]} />
      </div>

      <div className="container-editorial grid grid-cols-1 gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_1fr]">
        <div>
          <div className="overflow-hidden border border-taupe-200 bg-taupe-100">
            {gallery.length > 0 ? (
              <MediaImage
                media={gallery[activeImage]?.media}
                variant="large"
                mediaPath={gallery[activeImage]?.image}
                alt={product.name}
                width={900}
                height={900}
                aspect={1}
                priority
                className="aspect-square w-full object-cover"
              />
            ) : (
              <div className="flex aspect-square w-full items-center justify-center text-charcoal-600/40">No image</div>
            )}
          </div>
          {gallery.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {gallery.map((entry, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => setActiveImage(index)}
                  className={`h-16 w-16 shrink-0 overflow-hidden border ${activeImage === index ? 'border-burgundy-500' : 'border-taupe-300'}`}
                >
                  <MediaImage media={entry.media} variant="thumbnail" mediaPath={entry.image} alt="" width={120} height={120} aspect={1} className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="max-w-reading">
          {(product.category?.name || product.type) && <span className="eyebrow">{product.category?.name || product.type}</span>}
          <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{product.name}</h1>
          {product.shortDescription && <p className="mt-3 text-lg leading-relaxed text-charcoal-600">{product.shortDescription}</p>}

          {product.priceVisible && (
            <div className="mt-5 flex items-center gap-3">
              <span className="font-serif text-2xl font-semibold text-charcoal">
                {formatProductPrice(onSale ? product.salePrice : product.price, product.currency)}
              </span>
              {onSale && (
                <>
                  <span className="text-base text-charcoal-600/50 line-through">{formatProductPrice(product.price, product.currency)}</span>
                  {discountPercent != null && <span className="bg-burgundy-600 px-2 py-0.5 text-xs font-semibold text-ivory">-{discountPercent}%</span>}
                </>
              )}
            </div>
          )}

          <p className="mt-2 text-sm font-medium text-charcoal-600">
            {product.isAvailable ? 'Available' : product.status === 'archived' ? 'No longer available' : 'Currently unavailable'}
            {product.sku && <span className="ml-3 text-charcoal-600/60">SKU: {product.sku}</span>}
          </p>

          {canBuy ? (
            <a href={product.purchaseUrl} target="_blank" rel="noreferrer" onClick={handleCtaClick} className="btn-primary mt-5 inline-flex">
              <ShoppingBag size={16} /> {product.price === 0 ? 'Get it free' : 'Buy now'}
            </a>
          ) : (
            <div className="mt-5 inline-flex items-center gap-2 border border-taupe-300 bg-taupe-100 px-4 py-2.5 text-sm font-medium text-charcoal-600">
              <Clock size={15} />
              {product.isAvailable ? 'Coming soon' : 'Currently unavailable'}
            </div>
          )}

          {product.shippingNotes && product.type === 'physical' && <p className="mt-4 text-xs text-charcoal-600/70">{product.shippingNotes}</p>}

          {product.description?.length > 0 && (
            <div className="mt-10 border-t border-taupe-200 pt-8">
              <ArticleContent blocks={product.description} />
            </div>
          )}
        </div>
      </div>

      {more.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">You may also like</p>
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
            {more.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
