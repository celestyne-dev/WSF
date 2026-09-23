import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, Archive, Trash2, X } from 'lucide-react'
import {
  fetchResourceBySlug,
  createResource,
  updateResource,
  deleteResource,
} from '../../api/resources'
import { fetchAuthors, fetchTopics, fetchOrganizations } from '../../api/taxonomies'
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

const STATUSES = ['draft', 'review', 'scheduled', 'published', 'archived']
const RESOURCE_TYPES = [
  'Guide', 'Workbook', 'Template', 'Checklist', 'Planner', 'Toolkit',
  'Ebook', 'Worksheet', 'Report', 'Download', 'Video Resource', 'External Resource',
]
const ACCESS_TYPES = [
  { value: 'direct_download', label: 'Direct download — no gate' },
  { value: 'email_gate', label: 'Email-gated — capture name/email first' },
  { value: 'member_only', label: 'Member only — accounts not available yet' },
  { value: 'premium', label: 'Premium — purchasing not available yet' },
  { value: 'external_link', label: 'External link — hosted elsewhere' },
]
const FILE_FORMATS = ['PDF', 'DOCX', 'XLSX', 'PPTX', 'ZIP', 'Image', 'Video', 'Other']

function TagInput({ value, onChange }) {
  const [draft, setDraft] = useState('')

  function commit() {
    const slug = slugify(draft)
    if (slug && !value.includes(slug)) onChange([...value, slug])
    setDraft('')
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {value.map((tag) => (
          <span key={tag} className="inline-flex items-center gap-1 bg-taupe-100 px-2 py-1 text-xs text-charcoal-600">
            {tag}
            <button type="button" onClick={() => onChange(value.filter((t) => t !== tag))} aria-label={`Remove ${tag}`} className="hover:text-rose-600">
              <X size={11} />
            </button>
          </span>
        ))}
      </div>
      <div className="mt-1.5 flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commit()
            }
          }}
          placeholder="Add a tag and press Enter"
          className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
        />
        <button type="button" onClick={commit} className="btn-secondary shrink-0 !px-3 !py-2 text-xs">
          Add
        </button>
      </div>
    </div>
  )
}

function blankForm() {
  return {
    name: '',
    slug: '',
    subtitle: '',
    shortDescription: '',
    description: [],
    coverMedia: null,
    images: [],
    type: 'Guide',
    topicSlugs: [],
    tagSlugs: [],
    authorSlug: '',
    authorName: '',
    price: '',
    currency: 'USD',
    accessType: 'direct_download',
    fileUrl: '',
    externalUrl: '',
    fileFormat: '',
    fileSize: '',
    pageCount: '',
    sponsorSlug: '',
    sponsored: false,
    featured: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(resource) {
  return {
    name: resource.name || '',
    slug: resource.slug || '',
    subtitle: resource.subtitle || '',
    shortDescription: resource.shortDescription || '',
    description: resource.description || [],
    coverMedia: resource.coverMedia || null,
    images: resource.images || [],
    type: resource.type || 'Guide',
    topicSlugs: resource.topicSlugs || [],
    tagSlugs: resource.tagSlugs || [],
    authorSlug: resource.authorSlug || '',
    authorName: resource.authorName || '',
    price: resource.price ?? '',
    currency: resource.currency || 'USD',
    accessType: resource.accessType || 'direct_download',
    fileUrl: resource.fileUrl || '',
    externalUrl: resource.externalUrl || '',
    fileFormat: resource.fileFormat || '',
    fileSize: resource.fileSize ?? '',
    pageCount: resource.pageCount ?? '',
    sponsorSlug: resource.sponsorSlug || '',
    sponsored: !!resource.sponsored,
    featured: !!resource.featured,
    status: resource.status || 'draft',
    seoTitle: resource.seo?.title || '',
    seoDescription: resource.seo?.description || '',
    seoCanonical: resource.seo?.canonical || '',
    seoOgMedia: resource.seo?.ogImageMediaId ? { id: resource.seo.ogImageMediaId } : null,
    downloadCount: resource.downloadCount || 0,
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

export default function AdminResourceEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [topics, setTopics] = useState([])
  const [authors, setAuthors] = useState([])
  const [organizations, setOrganizations] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([
      fetchTopics(),
      fetchAuthors({ status: 'active', pageSize: 200 }),
      fetchOrganizations({ pageSize: 200 }),
      isNew ? Promise.resolve(null) : fetchResourceBySlug(id),
    ])
      .then(([topicList, authorRes, orgRes, existing]) => {
        if (!active) return
        setTopics(topicList)
        setAuthors(authorRes.items || authorRes)
        setOrganizations(orgRes.items || orgRes)
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the resource editor. Please try again.'))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isNew])

  function updateField(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'name' && !slugTouched) {
        next.slug = slugify(value)
      }
      return next
    })
  }

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a resource slug.`
    return null
  }

  const needsFileOrExternalUrl =
    form && ['direct_download', 'email_gate', 'external_link'].includes(form.accessType) && !form.fileUrl && !form.externalUrl

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (!form.name) {
      toast.error('Add a resource name.')
      return
    }
    if ((nextStatus === 'published' || nextStatus === 'scheduled') && form.description.length === 0) {
      toast.error('Add a description before publishing.')
      return
    }
    if ((nextStatus === 'published' || nextStatus === 'scheduled') && needsFileOrExternalUrl) {
      toast.error('Add a file URL or external URL before publishing.')
      return
    }
    setErrors({})
    setSaving(true)

    const payload = {
      name: form.name,
      slug: form.slug,
      subtitle: form.subtitle || null,
      shortDescription: form.shortDescription || null,
      description: form.description,
      coverMedia: form.coverMedia,
      images: form.images,
      type: form.type,
      topicSlugs: form.topicSlugs,
      tagSlugs: form.tagSlugs,
      authorSlug: form.authorSlug || null,
      authorName: form.authorSlug ? null : form.authorName || null,
      price: form.price,
      currency: form.currency,
      accessType: form.accessType,
      fileUrl: form.fileUrl || null,
      externalUrl: form.externalUrl || null,
      fileFormat: form.fileFormat || null,
      fileSize: form.fileSize,
      pageCount: form.pageCount,
      sponsorSlug: form.sponsorSlug || null,
      sponsored: form.sponsored,
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
      const saved = isNew ? await createResource(payload) : await updateResource(id, payload)
      toast.success(`Resource ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/resources/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this resource. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deleteResource(id)
      toast.success('Resource deleted.')
      navigate('/admin/resources')
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong deleting this resource.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the resource editor" description={loadError} />
  if (notFound) return <EmptyState title="Resource not found" description="This resource may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Resource' : `Edit: ${form.name || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/resources/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && form.status === 'published' && (
              <a href={`/resources/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Resource name">
              <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/resources/${form.slug || 'your-slug'}`}>
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
            <Field label="Subtitle" hint="optional — shown under the title on the detail page">
              <input value={form.subtitle} onChange={(e) => updateField('subtitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Short description" hint="shown on resource cards and search results">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Resource type">
              <select value={form.type} onChange={(e) => updateField('type', e.target.value)} className="w-full max-w-xs border border-taupe-300 px-3 py-2 text-sm">
                {RESOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
          </Section>

          <Section title="Main content" description="Structure this however makes sense — What's included, Who it's for, Key benefits, How to use it — you decide the headings.">
            <ArticleBlockEditor blocks={form.description} onChange={(description) => updateField('description', description)} />
          </Section>

          <Section title="Media">
            <MediaPicker label="Cover image" aspect={3 / 4} value={form.coverMedia} onChange={(media) => updateField('coverMedia', media)} />
            <GalleryEditor value={form.images} onChange={(images) => updateField('images', images)} />
          </Section>

          <Section title="File / access" description="How a visitor actually gets this resource.">
            <Field label="Access type">
              <select value={form.accessType} onChange={(e) => updateField('accessType', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                {ACCESS_TYPES.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </Field>
            {form.accessType === 'external_link' ? (
              <Field label="External URL">
                <input value={form.externalUrl} onChange={(e) => updateField('externalUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            ) : (
              <Field label="File URL" hint="link to the hosted download file">
                <input value={form.fileUrl} onChange={(e) => updateField('fileUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            )}
            {needsFileOrExternalUrl && <p className="text-xs text-rose-600">A file URL or external URL is required before publishing.</p>}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="File format" hint="optional">
                <select value={form.fileFormat} onChange={(e) => updateField('fileFormat', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {FILE_FORMATS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="File size (bytes)" hint="optional">
                <input type="number" min="0" value={form.fileSize} onChange={(e) => updateField('fileSize', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Page count" hint="optional">
                <input type="number" min="0" value={form.pageCount} onChange={(e) => updateField('pageCount', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="Pricing">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Price" hint="0 for a free resource">
                <input type="number" min="0" value={form.price} onChange={(e) => updateField('price', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Currency" hint="ISO code, e.g. USD, KES, EUR">
                <input value={form.currency} onChange={(e) => updateField('currency', e.target.value.toUpperCase().slice(0, 3))} className="w-full border border-taupe-300 px-3 py-2.5 text-sm uppercase focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
            {form.accessType === 'premium' && (
              <p className="text-xs text-charcoal-600/70">Purchasing isn't available yet — this resource will show a "coming soon" state publicly until the Shop supports it.</p>
            )}
          </Section>

          <Section title="Classification">
            <Field label="Topics">
              <div className="flex flex-wrap gap-2">
                {topics.map((t) => (
                  <button
                    key={t.slug}
                    type="button"
                    onClick={() => toggleTopic(t.slug)}
                    className={`px-2.5 py-1 text-xs font-medium ${form.topicSlugs.includes(t.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                  >
                    {t.name}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Tags">
              <TagInput value={form.tagSlugs} onChange={(tagSlugs) => updateField('tagSlugs', tagSlugs)} />
            </Field>
            <Field label="Author" hint="optional — links to an existing Author profile">
              <select
                value={form.authorSlug}
                onChange={(e) => updateField('authorSlug', e.target.value)}
                className="w-full border border-taupe-300 px-3 py-2 text-sm"
              >
                <option value="">— None —</option>
                {authors.map((a) => (
                  <option key={a.slug} value={a.slug}>
                    {a.name}
                  </option>
                ))}
              </select>
            </Field>
            {!form.authorSlug && (
              <Field label="Author name" hint="optional — freeform fallback when no Author profile is linked (e.g. 'WSF Editorial Team')">
                <input value={form.authorName} onChange={(e) => updateField('authorName', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            )}
          </Section>

          <Section title="Promotion">
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
              Featured
            </label>
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.sponsored} onChange={(e) => updateField('sponsored', e.target.checked)} />
              Sponsored
            </label>
            {form.sponsored && (
              <Field label="Sponsor" hint="shown as a disclosure on the public resource page">
                <select value={form.sponsorSlug} onChange={(e) => updateField('sponsorSlug', e.target.value)} className="w-full max-w-sm border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {organizations.map((o) => (
                    <option key={o.slug} value={o.slug}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the resource name">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the short description">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint="only set this if this resource is republished from elsewhere">
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
              <button type="button" onClick={() => handleSave('published')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                Publish
              </button>
              {!isNew && form.status !== 'archived' && (
                <button type="button" onClick={() => handleSave('archived')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  <Archive size={13} /> Archive
                </button>
              )}
              {!isNew && (
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  <Trash2 size={13} className="mr-1 inline" /> Delete resource
                </button>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Downloads</p>
            <p className="mt-2 text-2xl font-semibold text-charcoal">{form.downloadCount ?? 0}</p>
            <p className="mt-1 text-xs text-charcoal-600/70">Total successful downloads / access grants for this resource.</p>
          </div>

          <Link to="/admin/resources" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all resources
          </Link>
        </div>
      </div>
    </div>
  )
}
