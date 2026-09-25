import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, ShieldCheck, History, CheckCircle2 } from 'lucide-react'
import { fetchPageAdmin, createPage, updatePage, setPageStatus, markPageReviewed, deletePage, fetchPageRevisions } from '../../api/pages'
import { RESERVED_SLUGS } from '../../constants/routes'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import MediaPicker from '../../components/cms/MediaPicker'
import ArticleBlockEditor from '../../components/cms/ArticleBlockEditor'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

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
    title: '',
    slug: '',
    internalName: '',
    subtitle: '',
    content: [],
    heroMedia: null,
    status: 'draft',
    effectiveDate: '',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(page) {
  return {
    title: page.title || '',
    slug: page.slug || '',
    internalName: page.internalName || '',
    subtitle: page.subtitle || '',
    content: page.content || [],
    heroMedia: page.heroMediaId ? { ...page.heroMedia, id: page.heroMediaId } : null,
    status: page.status || 'draft',
    effectiveDate: page.effectiveDate || '',
    seoTitle: page.seo?.title || '',
    seoDescription: page.seo?.description || '',
    seoCanonical: page.seo?.canonical || '',
    seoOgMedia: page.seo?.ogImageMediaId ? { id: page.seo.ogImageMediaId } : null,
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

export default function AdminPageEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [page, setPage] = useState(null)
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [revisions, setRevisions] = useState([])
  const [reviewing, setReviewing] = useState(false)

  useEffect(() => {
    let active = true
    if (isNew) {
      setForm(blankForm())
      return
    }
    fetchPageAdmin(id)
      .then((existing) => {
        if (!active) return
        if (existing) {
          setPage(existing)
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading the page editor. Please try again.')
      })
    fetchPageRevisions(id)
      .then((res) => active && setRevisions(res))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [id, isNew])

  const isSystem = page?.isSystem

  function updateField(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'title' && !slugTouched && !isSystem) {
        next.slug = slugify(value)
      }
      return next
    })
  }

  function validateSlug(slug) {
    if (isSystem) return null
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a page slug.`
    return null
  }

  function buildPayload() {
    const payload = {
      title: form.title,
      internalName: form.internalName || null,
      subtitle: form.subtitle || null,
      content: form.content,
      heroMediaId: form.heroMedia?.id || null,
      effectiveDate: form.effectiveDate || null,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
    }
    if (!isSystem) payload.slug = form.slug
    return payload
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
        const created = await createPage({ ...buildPayload(), status: nextStatus })
        toast.success(`Page ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
        navigate(`/admin/pages/${created.id}`)
      } else {
        let saved = await updatePage(id, buildPayload())
        if (nextStatus !== saved.status) saved = await setPageStatus(id, nextStatus)
        toast.success(`Page ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
        setPage(saved)
        setForm(toForm(saved))
        fetchPageRevisions(id).then(setRevisions).catch(() => {})
      }
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong saving this page. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleMarkReviewed() {
    setReviewing(true)
    try {
      const saved = await markPageReviewed(id)
      toast.success('Marked as reviewed.')
      setPage(saved)
      setForm(toForm(saved))
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setReviewing(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete "${form.title}"? This can't be undone.`)) return
    try {
      await deletePage(id)
      toast.success('Page deleted.')
      navigate('/admin/pages')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || "This page is protected and can't be deleted.")
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the page editor" description={loadError} />
  if (notFound) return <EmptyState title="Page not found" description="This page may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Page' : `Edit: ${form.title || 'Untitled'}`}
        description={isSystem ? `Public URL: womenshapingfutures.org/${form.slug} — fixed, can't be changed` : `Public URL: womenshapingfutures.org/${form.slug || 'your-slug'}`}
        actions={
          <>
            {isSystem && (
              <span className="inline-flex items-center gap-1 border border-burgundy-200 bg-burgundy-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-burgundy-700">
                <ShieldCheck size={12} /> System page
              </span>
            )}
            <StatusBadge status={form.status} />
            {!isNew && form.status === 'published' && (
              <a href={`/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Title">
              <input value={form.title} onChange={(e) => updateField('title', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field
              label="Slug"
              hint={isSystem ? "fixed to this page's route" : `public URL: womenshapingfutures.org/${form.slug || 'your-slug'}`}
            >
              <input
                value={form.slug}
                disabled={isSystem}
                onChange={(e) => {
                  setSlugTouched(true)
                  updateField('slug', slugify(e.target.value))
                }}
                className={`w-full border px-3 py-2.5 text-sm focus:outline-none ${isSystem ? 'bg-taupe-100 text-charcoal-600/70' : errors.slug ? 'border-rose-500' : 'border-taupe-300 focus:border-burgundy-500'}`}
              />
              {errors.slug && <p className="mt-1 text-xs text-rose-600">{errors.slug}</p>}
            </Field>
            <Field label="Internal name" hint="admin-only label, defaults to the title above">
              <input value={form.internalName} onChange={(e) => updateField('internalName', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Subtitle / intro" hint="shown under the title on the public page">
              <textarea rows={2} value={form.subtitle} onChange={(e) => updateField('subtitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Content">
            <ArticleBlockEditor blocks={form.content} onChange={(content) => updateField('content', content)} />
          </Section>

          <Section title="Media" description="Hero image — most legal pages don't need one. Rendered inside a controlled container — never cropped or stretched.">
            <MediaPicker label="Hero image" aspect={16 / 9} value={form.heroMedia} onChange={(media) => updateField('heroMedia', media)} />
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the page's title">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the subtitle">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint={isSystem ? 'leave blank — the public route is already canonical' : 'only set this if this page is republished from elsewhere'}>
              <input value={form.seoCanonical} onChange={(e) => updateField('seoCanonical', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <MediaPicker label="Social / OG image" aspect={1.91 / 1} value={form.seoOgMedia} onChange={(media) => updateField('seoOgMedia', media)} />
          </Section>

          <Section title="Legal / effective date" description="Shown publicly as “Last updated” on legal pages. Never auto-derived — set it only when the substance of this page actually changes.">
            <Field label="Effective / last updated date" hint="optional">
              <input type="date" value={form.effectiveDate} onChange={(e) => updateField('effectiveDate', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none sm:w-64" />
            </Field>
            {!isNew && (
              <div className="flex items-center justify-between border-t border-taupe-200 pt-4">
                <div className="text-xs text-charcoal-600">
                  {page?.lastReviewedAt ? (
                    <>
                      Last reviewed {formatDate(page.lastReviewedAt)}
                      {page.lastReviewedBy?.full_name && ` by ${page.lastReviewedBy.full_name}`}
                    </>
                  ) : (
                    'Not yet marked as reviewed.'
                  )}
                </div>
                <button type="button" onClick={handleMarkReviewed} disabled={reviewing} className="btn-secondary !px-3 !py-1.5 text-xs disabled:opacity-60">
                  <CheckCircle2 size={13} /> {reviewing ? 'Saving…' : 'Mark as reviewed'}
                </button>
              </div>
            )}
          </Section>

          {!isNew && revisions.length > 0 && (
            <Section title="Revision history" description="Who changed this page and when — view only.">
              <ul className="divide-y divide-taupe-200">
                {revisions.map((r) => (
                  <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="flex items-center gap-2 text-charcoal-600">
                      <History size={13} /> {r.note || 'Updated'}
                      {r.createdBy?.full_name && ` — ${r.createdBy.full_name}`}
                    </span>
                    <span className="text-xs text-charcoal-600/70">{formatDate(r.createdAt)}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
            <select value={form.status} onChange={(e) => updateField('status', e.target.value)} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm">
              {STATUSES.filter((s) => !(isSystem && s === 'archived')).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            {isSystem && <p className="mt-2 text-xs text-charcoal-600/70">Required system pages can't be archived — use draft to take one offline temporarily.</p>}

            <div className="mt-4 space-y-2">
              <button type="button" onClick={() => handleSave('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                <Save size={13} /> {saving ? 'Saving…' : 'Save draft'}
              </button>
              <button type="button" onClick={() => handleSave('published')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                Publish
              </button>
              {!isNew && !isSystem && (
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  Delete page
                </button>
              )}
              {!isNew && isSystem && (
                <p className="pt-1 text-center text-[11px] text-charcoal-600/60">Required system pages can't be deleted.</p>
              )}
            </div>
          </div>

          <Link to="/admin/pages" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all pages
          </Link>
        </div>
      </div>
    </div>
  )
}
