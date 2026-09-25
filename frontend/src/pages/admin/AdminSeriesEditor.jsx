import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, Archive, Trash2 } from 'lucide-react'
import { fetchSeriesAdminById, createSeries, updateSeries, setSeriesStatus, deleteSeries, fetchOrganizations } from '../../api/taxonomies'
import { RESERVED_SLUGS } from '../../constants/routes'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import MediaPicker from '../../components/cms/MediaPicker'
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

const STATUSES = ['draft', 'published', 'archived']

function blankForm() {
  return {
    name: '',
    slug: '',
    subtitle: '',
    description: '',
    coverMedia: null,
    sponsorOrganizationId: '',
    sortOrder: 0,
    featured: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(series) {
  return {
    name: series.name || '',
    slug: series.slug || '',
    subtitle: series.subtitle || '',
    description: series.description || '',
    coverMedia: series.coverMedia,
    sponsorOrganizationId: series.sponsor?.id || '',
    sortOrder: series.sortOrder || 0,
    featured: !!series.featured,
    status: series.status || 'draft',
    seoTitle: series.seo?.title || '',
    seoDescription: series.seo?.description || '',
    seoCanonical: series.seo?.canonical || '',
    seoOgMedia: series.seo?.ogImageMediaId ? { id: series.seo.ogImageMediaId } : null,
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

export default function AdminSeriesEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [organizations, setOrganizations] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [usageCount, setUsageCount] = useState(0)

  useEffect(() => {
    let active = true
    Promise.all([fetchOrganizations({ pageSize: 200 }), isNew ? Promise.resolve(null) : fetchSeriesAdminById(id)])
      .then(([orgResult, existing]) => {
        if (!active) return
        setOrganizations(orgResult.items)
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
          setUsageCount(existing.usageCount || 0)
        } else {
          setNotFound(true)
        }
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading the series editor. Please try again.')
      })
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

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a series slug.`
    return null
  }

  function buildPayload() {
    return {
      name: form.name,
      slug: form.slug,
      subtitle: form.subtitle || null,
      description: form.description || null,
      coverMediaId: form.coverMedia?.id || null,
      sponsorOrganizationId: form.sponsorOrganizationId || null,
      sortOrder: Number(form.sortOrder) || 0,
      featured: form.featured,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
    }
  }

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    setErrors({})
    setSaving(true)

    try {
      if (isNew) {
        const created = await createSeries({ ...buildPayload(), status: nextStatus })
        toast.success(`Series ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
        navigate(`/admin/taxonomy/series/${created.id}`)
      } else {
        let saved = await updateSeries(id, buildPayload())
        if (nextStatus !== saved.status) saved = await setSeriesStatus(id, nextStatus)
        toast.success(`Series ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
        setForm(toForm(saved))
      }
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong saving this series. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deleteSeries(id)
      toast.success('Series deleted.')
      navigate('/admin/taxonomy/series')
    } catch (err) {
      const message = err?.response?.data?.error?.message || "This series is referenced elsewhere and can't be deleted. Try archiving instead."
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the series editor" description={loadError} />
  if (notFound) return <EmptyState title="Series not found" description="This series may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Series' : `Edit: ${form.name || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/series/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.status === 'published' && (
              <a href={`/series/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Series name">
              <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/series/${form.slug || 'your-slug'} — stays fixed after creation`}>
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
            <Field label="Subtitle" hint="optional, shown under the series name">
              <input value={form.subtitle} onChange={(e) => updateField('subtitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Description">
              <textarea rows={3} value={form.description} onChange={(e) => updateField('description', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Sponsor organization" hint="optional">
                <select value={form.sponsorOrganizationId} onChange={(e) => updateField('sponsorOrganizationId', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {organizations.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Display order" hint="lower numbers appear first">
                <input type="number" value={form.sortOrder} onChange={(e) => updateField('sortOrder', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="Cover image" description="Shown at the top of the public series page. Rendered inside a controlled container — never cropped or stretched.">
            <MediaPicker label="Cover image" aspect={16 / 9} value={form.coverMedia} onChange={(media) => updateField('coverMedia', media)} />
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the series' name">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the description">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint="only set this if this page is republished from elsewhere">
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
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
              Featured
            </label>

            {!isNew && (
              <p className="mt-3 text-xs text-charcoal-600">
                Used by <span className="font-semibold text-charcoal">{usageCount}</span> item{usageCount === 1 ? '' : 's'}.
                {usageCount > 0 && ' Referenced content can\'t be deleted — archive instead.'}
              </p>
            )}

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
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={usageCount > 0}
                  className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline disabled:cursor-not-allowed disabled:text-charcoal-600/40 disabled:no-underline"
                >
                  <Trash2 size={13} className="mr-1 inline" /> Delete series
                </button>
              )}
            </div>
          </div>

          <Link to="/admin/taxonomy/series" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all series
          </Link>
        </div>
      </div>
    </div>
  )
}
