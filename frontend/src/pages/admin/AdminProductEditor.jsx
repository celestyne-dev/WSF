import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, Archive, Trash2 } from 'lucide-react'
import { fetchProductBySlug, createProduct, updateProduct, deleteProduct, fetchProductCategories, createProductCategory } from '../../api/products'
import { fetchResources } from '../../api/resources'
import { RESERVED_SLUGS } from '../../constants/routes'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import MediaPicker from '../../components/cms/MediaPicker'
import GalleryEditor from '../../components/cms/GalleryEditor'
import ArticleBlockEditor from '../../components/cms/ArticleBlockEditor'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

const STATUSES = ['draft', 'active', 'unavailable', 'archived']
const TYPES = [
  { value: 'digital', label: 'Digital' },
  { value: 'downloadable', label: 'Downloadable' },
  { value: 'physical', label: 'Physical' },
  { value: 'service', label: 'Service' },
  { value: 'other', label: 'Other' },
]

function blankForm() {
  return {
    name: '',
    slug: '',
    shortDescription: '',
    description: [],
    type: 'digital',
    sku: '',
    category: null,
    resourceSlug: '',
    coverMedia: null,
    images: [],
    price: '',
    salePrice: '',
    currency: 'USD',
    priceVisible: true,
    trackInventory: false,
    stockQuantity: '',
    shippingNotes: '',
    purchaseUrl: '',
    featured: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(product) {
  return {
    name: product.name || '',
    slug: product.slug || '',
    shortDescription: product.shortDescription || '',
    description: product.description || [],
    type: product.type || 'digital',
    sku: product.sku || '',
    category: product.category || null,
    resourceSlug: product.resourceSlug || '',
    coverMedia: product.coverMedia || null,
    images: product.images || [],
    price: product.price ?? '',
    salePrice: product.salePrice ?? '',
    currency: product.currency || 'USD',
    priceVisible: product.priceVisible !== false,
    trackInventory: !!product.trackInventory,
    stockQuantity: product.stockQuantity ?? '',
    shippingNotes: product.shippingNotes || '',
    purchaseUrl: product.purchaseUrl || '',
    featured: !!product.featured,
    status: product.status || 'draft',
    seoTitle: product.seo?.title || '',
    seoDescription: product.seo?.description || '',
    seoCanonical: product.seo?.canonical || '',
    seoOgMedia: product.seo?.ogImageMediaId ? { id: product.seo.ogImageMediaId } : null,
  }
}

function Section({ title, description, children }) {
  return (
    <div className="border border-taupe-200 bg-white p-6">
      <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{title}</p>
      {description && <p className="mt-0.5 text-xs text-charcoal-600/70">{description}</p>}
      <div className="mt-3 space-y-4">{children}</div>
    </div>
  )
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
        {label} {hint && <span className="normal-case text-charcoal-600/60">— {hint}</span>}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

export default function AdminProductEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [categories, setCategories] = useState([])
  const [newCategoryName, setNewCategoryName] = useState('')
  const [resourceSearch, setResourceSearch] = useState('')
  const [resources, setResources] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchProductCategories(), isNew ? Promise.resolve(null) : fetchProductBySlug(id)])
      .then(([cats, existing]) => {
        if (!active) return
        setCategories(cats)
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the product editor. Please try again.'))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isNew])

  useEffect(() => {
    if (!resourceSearch) {
      setResources([])
      return
    }
    let active = true
    fetchResources({ pageSize: 20, query: resourceSearch }).then((res) => active && setResources(res.items)).catch(() => {})
    return () => {
      active = false
    }
  }, [resourceSearch])

  function updateField(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'name' && !slugTouched) {
        next.slug = slugify(value)
      }
      if (field === 'type' && value !== 'physical') {
        next.shippingNotes = ''
      }
      return next
    })
  }

  async function handleAddCategory() {
    if (!newCategoryName.trim()) return
    try {
      const category = await createProductCategory(newCategoryName.trim())
      setCategories((prev) => [...prev, category])
      updateField('category', category)
      setNewCategoryName('')
      toast.success('Category created.')
    } catch (err) {
      toast.error(err.apiError?.message || 'Something went wrong creating this category.')
    }
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a product slug.`
    return null
  }

  const salePriceInvalid = form && form.salePrice !== '' && form.price !== '' && Number(form.salePrice) > Number(form.price)
  const stockInvalid = form && form.trackInventory && form.stockQuantity !== '' && Number(form.stockQuantity) < 0

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (!form.name) {
      toast.error('Add a product name.')
      return
    }
    if (form.price === '' || Number(form.price) < 0) {
      toast.error('Set a price of 0 or more (0 for a free product).')
      return
    }
    if (salePriceInvalid) {
      toast.error('Sale price cannot exceed the regular price.')
      return
    }
    if (stockInvalid) {
      toast.error('Stock quantity cannot be negative.')
      return
    }
    setErrors({})
    setSaving(true)

    const payload = {
      name: form.name,
      slug: form.slug,
      shortDescription: form.shortDescription || null,
      description: form.description,
      type: form.type,
      sku: form.sku || null,
      category: form.category,
      resourceSlug: form.resourceSlug || null,
      coverMedia: form.coverMedia,
      images: form.images,
      price: form.price,
      salePrice: form.salePrice,
      currency: form.currency,
      priceVisible: form.priceVisible,
      trackInventory: form.trackInventory,
      stockQuantity: form.trackInventory ? form.stockQuantity : '',
      shippingNotes: form.shippingNotes || null,
      purchaseUrl: form.purchaseUrl || null,
      featured: form.featured,
      status: nextStatus,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
    }

    try {
      const saved = isNew ? await createProduct(payload) : await updateProduct(id, payload)
      toast.success(`Product ${nextStatus === 'active' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/products/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this product. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deleteProduct(id)
      toast.success('Product deleted.')
      navigate('/admin/products')
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong deleting this product.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the product editor" description={loadError} />
  if (notFound) return <EmptyState title="Product not found" description="This product may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Product' : `Edit: ${form.name || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/shop/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && form.status === 'active' && (
              <a href={`/shop/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Product name">
              <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/shop/${form.slug || 'your-slug'}`}>
              <input
                value={form.slug}
                onChange={(e) => {
                  setSlugTouched(true)
                  updateField('slug', slugify(e.target.value))
                }}
                className={`w-full border px-3 py-2.5 text-sm focus:outline-none ${errors.slug ? 'border-rose-500' : 'border-taupe-300 focus:border-burgundy-500'}`}
              />
              {errors.slug && <p className="mt-1 text-xs text-rose-600">{errors.slug}</p>}
            </Field>
            <Field label="Short description" hint="shown on shop cards">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="SKU" hint="optional, internal — for product management only">
              <input value={form.sku} onChange={(e) => updateField('sku', e.target.value)} className="w-full max-w-xs border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Description" description="Structure the content however makes sense — About, What's included, Who it's for, Specifications — you decide the headings.">
            <ArticleBlockEditor blocks={form.description} onChange={(description) => updateField('description', description)} />
          </Section>

          <Section title="Product type">
            <Field label="Type">
              <select value={form.type} onChange={(e) => updateField('type', e.target.value)} className="w-full max-w-xs border border-taupe-300 px-3 py-2 text-sm">
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </Field>
          </Section>

          <Section title="Category">
            <Field label="Category" hint="optional">
              <select
                value={form.category?.id || ''}
                onChange={(e) => updateField('category', categories.find((c) => String(c.id) === e.target.value) || null)}
                className="w-full max-w-xs border border-taupe-300 px-3 py-2 text-sm"
              >
                <option value="">— None —</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="flex items-end gap-2">
              <Field label="Add a new category">
                <input value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} placeholder="e.g. Workbooks" className="w-56 border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <button type="button" onClick={handleAddCategory} className="btn-secondary !px-3 !py-2 text-xs">
                Add
              </button>
            </div>
          </Section>

          <Section title="Media / gallery">
            <MediaPicker label="Primary image" aspect={1} value={form.coverMedia} onChange={(media) => updateField('coverMedia', media)} />
            <GalleryEditor value={form.images} onChange={(images) => updateField('images', images)} />
          </Section>

          <Section title="Pricing">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Price" hint="0 for a free product">
                <input type="number" min="0" value={form.price} onChange={(e) => updateField('price', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Sale price" hint="optional">
                <input type="number" min="0" value={form.salePrice} onChange={(e) => updateField('salePrice', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Currency" hint="ISO code, e.g. USD, KES, EUR">
                <input value={form.currency} onChange={(e) => updateField('currency', e.target.value.toUpperCase().slice(0, 3))} className="w-full border border-taupe-300 px-3 py-2.5 text-sm uppercase focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
            {salePriceInvalid && <p className="text-xs text-rose-600">Sale price cannot exceed the regular price.</p>}
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.priceVisible} onChange={(e) => updateField('priceVisible', e.target.checked)} />
              Show price publicly
            </label>
          </Section>

          <Section title="Inventory / availability">
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.trackInventory} onChange={(e) => updateField('trackInventory', e.target.checked)} />
              Track inventory for this product
            </label>
            {form.trackInventory && (
              <Field label="Stock quantity">
                <input type="number" min="0" value={form.stockQuantity} onChange={(e) => updateField('stockQuantity', e.target.value)} className="w-full max-w-xs border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
                {stockInvalid && <p className="mt-1 text-xs text-rose-600">Stock quantity cannot be negative.</p>}
              </Field>
            )}
            {form.type === 'physical' && (
              <Field label="Shipping notes" hint="optional — no shipping cost calculation, just informational notes">
                <textarea rows={2} value={form.shippingNotes} onChange={(e) => updateField('shippingNotes', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            )}
          </Section>

          <Section title="Purchase / action" description="Where a shopper goes to buy this product. Leave blank to show a professional 'coming soon' state instead of a broken Buy button.">
            <Field label="Purchase URL" hint="e.g. an external checkout link">
              <input value={form.purchaseUrl} onChange={(e) => updateField('purchaseUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Linked resource" hint="optional — reuses an existing downloadable Resource's file for delivery">
              <input value={resourceSearch} onChange={(e) => setResourceSearch(e.target.value)} placeholder="Search resources…" className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
              {form.resourceSlug && <p className="mt-1 text-xs text-charcoal-600">Linked: {form.resourceSlug}</p>}
              {resources.length > 0 && (
                <div className="mt-1.5 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto border border-taupe-200 p-2">
                  {resources.map((r) => (
                    <button
                      key={r.slug}
                      type="button"
                      onClick={() => {
                        updateField('resourceSlug', r.slug)
                        setResourceSearch('')
                        setResources([])
                      }}
                      className="bg-taupe-100 px-2.5 py-1 text-xs font-medium text-charcoal-600 hover:bg-plum-600 hover:text-ivory"
                    >
                      {r.name}
                    </button>
                  ))}
                </div>
              )}
              {form.resourceSlug && (
                <button type="button" onClick={() => updateField('resourceSlug', '')} className="mt-1 text-xs text-charcoal-600/70 hover:text-burgundy-600">
                  Remove link
                </button>
              )}
            </Field>
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the product name">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the short description">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint="only set this if this listing is republished from elsewhere">
              <input value={form.seoCanonical} onChange={(e) => updateField('seoCanonical', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <MediaPicker label="Social / OG image" aspect={1.91 / 1} value={form.seoOgMedia} onChange={(media) => updateField('seoOgMedia', media)} />
          </Section>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
            <select value={form.status} onChange={(e) => updateField('status', e.target.value)} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>

            <div className="mt-4 space-y-2">
              <button type="button" onClick={() => handleSave('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                <Save size={13} /> {saving ? 'Saving…' : 'Save draft'}
              </button>
              <button type="button" onClick={() => handleSave('active')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                Publish
              </button>
              {!isNew && form.status !== 'unavailable' && (
                <button type="button" onClick={() => handleSave('unavailable')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  Mark unavailable
                </button>
              )}
              {!isNew && form.status !== 'archived' && (
                <button type="button" onClick={() => handleSave('archived')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  <Archive size={13} /> Archive
                </button>
              )}
              {!isNew && (
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  <Trash2 size={13} className="mr-1 inline" /> Delete product
                </button>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Featured</p>
            <p className="mt-1 text-xs text-charcoal-600/70">Lets the Shop (and later, the homepage) highlight this product.</p>
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
              Featured
            </label>
          </div>

          <Link to="/admin/products" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all products
          </Link>
        </div>
      </div>
    </div>
  )
}
