import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, Archive, Trash2 } from 'lucide-react'
import { fetchTopicAdmin, createTopic, updateTopic, setTopicStatus, deleteTopic } from '../../api/taxonomies'
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
    description: '',
    heroMedia: null,
    sortOrder: 0,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(topic) {
  return {
    name: topic.name || '',
    slug: topic.slug || '',
    description: topic.description || '',
    heroMedia: topic.heroMediaId ? { ...topic.heroMedia, id: topic.heroMediaId } : null,
    sortOrder: topic.sortOrder || 0,
    status: topic.status || 'draft',
    seoTitle: topic.seo?.title || '',
    seoDescription: topic.seo?.description || '',
    seoCanonical: topic.seo?.canonical || '',
    seoOgMedia: topic.seo?.ogImageMediaId ? { id: topic.seo.ogImageMediaId } : null,
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

export default function AdminTopicEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [usageCount, setUsageCount] = useState(0)

  useEffect(() => {
    let active = true
    if (isNew) {
      setForm(blankForm())
      return
    }
    fetchTopicAdmin(id)
      .then((existing) => {
        if (!active) return
        if (existing) {
          setForm(toForm(existing))
          setUsageCount(existing.usageCount || 0)
        } else {
          setNotFound(true)
        }
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading the topic editor. Please try again.')
      })
    return () => {
      active = false
    }
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
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a topic slug.`
    return null
  }

  function buildPayload() {
    return {
      name: form.name,
      slug: form.slug,
      description: form.description || null,
      heroMediaId: form.heroMedia?.id || null,
      sortOrder: Number(form.sortOrder) || 0,
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
        const created = await createTopic({ ...buildPayload(), status: nextStatus })
        toast.success(`Topic ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
        navigate(`/admin/taxonomy/topics/${created.id}`)
      } else {
        let saved = await updateTopic(id, buildPayload())
        if (nextStatus !== saved.status) saved = await setTopicStatus(id, nextStatus)
        toast.success(`Topic ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
        setForm(toForm(saved))
      }
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong saving this topic. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deleteTopic(id)
      toast.success('Topic deleted.')
      navigate('/admin/taxonomy/topics')
    } catch (err) {
      const message = err?.response?.data?.error?.message || "This topic is referenced elsewhere and can't be deleted. Try archiving instead."
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the topic editor" description={loadError} />
  if (notFound) return <EmptyState title="Topic not found" description="This topic may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Topic' : `Edit: ${form.name || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/topics/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.status === 'published' && (
              <a href={`/topics/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Topic name">
              <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/topics/${form.slug || 'your-slug'} — stays fixed after creation`}>
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
            <Field label="Description">
              <textarea rows={3} value={form.description} onChange={(e) => updateField('description', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Display order" hint="lower numbers appear first">
              <input
                type="number"
                value={form.sortOrder}
                onChange={(e) => updateField('sortOrder', e.target.value)}
                className="w-32 border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
              />
            </Field>
          </Section>

          <Section title="Hero image" description="Shown at the top of the public topic page. Rendered inside a controlled container — never cropped or stretched.">
            <MediaPicker label="Hero image" aspect={16 / 9} value={form.heroMedia} onChange={(media) => updateField('heroMedia', media)} />
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the topic's name">
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
                  <Trash2 size={13} className="mr-1 inline" /> Delete topic
                </button>
              )}
            </div>
          </div>

          <Link to="/admin/taxonomy/topics" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all topics
          </Link>
        </div>
      </div>
    </div>
  )
}
