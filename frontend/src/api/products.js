import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// The mock products dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockProducts
async function loadMockProducts() {
  if (!_mockProducts) _mockProducts = await import('../mock/products')
  return _mockProducts
}

function mapProductCategory(c) {
  if (!c) return null
  return { id: c.id, slug: c.slug, name: c.name, description: c.description || '' }
}

function mapProductImage(img) {
  if (!img) return null
  // mapMediaRef() strips `id` (most callers only ever display media, never
  // resend it) — the gallery editor needs it back to reconstruct
  // galleryMediaIds on save, so it's restored here rather than widening
  // mapMediaRef for every other caller.
  return { id: img.id, position: img.position, media: { ...mapMediaRef(img.media), id: img.media?.id } }
}

export function mapProduct(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    name: p.name,
    shortDescription: p.short_description || p.shortDescription || '',
    description: Array.isArray(p.description) ? p.description : [],
    type: p.type,
    sku: p.sku || null,
    category: mapProductCategory(p.category) || p.category || null,
    categoryId: p.category_id ?? p.categoryId ?? null,
    resourceSlug: p.resource?.slug || null,
    price: p.price,
    salePrice: p.sale_price ?? p.salePrice ?? null,
    currency: p.currency || 'USD',
    priceVisible: p.price_visible ?? p.priceVisible ?? true,
    trackInventory: p.track_inventory ?? p.trackInventory ?? false,
    stockQuantity: p.stock_quantity ?? p.stockQuantity ?? null,
    shippingNotes: p.shipping_notes || p.shippingNotes || '',
    purchaseUrl: p.purchase_url || p.purchaseUrl || null,
    featured: !!p.featured,
    status: p.status,
    isAvailable: p.is_available ?? p.isAvailable ?? false,
    publishedDate: p.published_date || p.publishedDate || null,
    seo: p.seo || null,
    coverImage: p.cover_media?.public_url || p.coverImage || null,
    coverMedia: mapMediaRef(p.cover_media) || p.coverMedia || null,
    images: Array.isArray(p.images) ? p.images.map(mapProductImage) : [],
  }
}

export async function fetchProducts(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/products', { params })
    return { ...data, items: data.items.map(mapProduct) }
  }
  const { products } = await loadMockProducts()
  let results = products.filter((p) => p.status === 'active' || p.status === 'unavailable')
  if (params.type) results = results.filter((p) => p.type === params.type)
  if (params.category) results = results.filter((p) => p.category?.slug === params.category)
  if (params.featured === 'true' || params.featured === true) results = results.filter((p) => p.featured)
  if (params.free === 'true' || params.free === true) results = results.filter((p) => !p.price)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((p) => p.name.toLowerCase().includes(q))
  }
  results = results.map(mapProduct)
  const page = paginate(results, params)
  return delay(page)
}

export async function fetchProductBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/products/${slug}`)
      return mapProduct(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getProductBySlug } = await loadMockProducts()
  return delay(mapProduct(getProductBySlug(slug)))
}

export async function fetchProductCategories() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/products/categories')
    return data.map(mapProductCategory)
  }
  const { productCategories } = await loadMockProducts()
  return delay(productCategories.map(mapProductCategory))
}

export async function createProductCategory(name) {
  const { data } = await apiClient.post('/products/categories', { name })
  return mapProductCategory(data)
}

function toApiPayload(form) {
  return {
    name: form.name,
    slug: form.slug || undefined,
    shortDescription: form.shortDescription || undefined,
    description: form.description || [],
    coverMediaId: form.coverMedia?.id || undefined,
    galleryMediaIds: (form.images || []).map((img) => img.media?.id || img.id).filter(Boolean),
    resourceSlug: form.resourceSlug || undefined,
    categoryId: form.category?.id || form.categoryId || undefined,
    type: form.type || undefined,
    sku: form.sku || undefined,
    price: form.price === '' || form.price == null ? 0 : Number(form.price),
    salePrice: form.salePrice === '' || form.salePrice == null ? undefined : Number(form.salePrice),
    currency: form.currency || undefined,
    priceVisible: form.priceVisible !== false,
    trackInventory: !!form.trackInventory,
    stockQuantity:
      form.stockQuantity === '' || form.stockQuantity == null ? undefined : Number(form.stockQuantity),
    shippingNotes: form.shippingNotes || undefined,
    purchaseUrl: form.purchaseUrl || undefined,
    featured: !!form.featured,
    status: form.status || 'draft',
    publishedDate: form.publishedDate || undefined,
    seo: form.seo || undefined,
  }
}

export async function createProduct(form) {
  const { data } = await apiClient.post('/products', toApiPayload(form))
  return mapProduct(data)
}

export async function updateProduct(slug, form) {
  const { data } = await apiClient.put(`/products/${slug}`, toApiPayload(form))
  return mapProduct(data)
}

export async function deleteProduct(slug) {
  await apiClient.delete(`/products/${slug}`)
}
