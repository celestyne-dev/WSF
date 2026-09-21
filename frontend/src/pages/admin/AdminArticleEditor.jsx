import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye } from 'lucide-react'
import { fetchArticleBySlug, createArticle, updateArticle } from '../../api/articles'
import { fetchAuthors, fetchTopics } from '../../api/taxonomies'
import { RESERVED_SLUGS } from '../../mock'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
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

const STATUSES = ['draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published', 'archived']

function blankForm(defaultAuthorSlug) {
  return {
    title: '',
    slug: '',
    subtitle: '',
    excerpt: '',
    heroImage: '',
    authorSlug: defaultAuthorSlug || '',
    topicSlugs: [],
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    isSponsored: false,
  }
}

function toForm(article) {
  return {
    title: article.title || '',
    slug: article.slug || '',
    subtitle: article.subtitle || '',
    excerpt: article.excerpt || '',
    heroImage: article.heroImage || '',
    authorSlug: article.authorSlug || article.author?.slug || '',
    topicSlugs: article.topicSlugs || [],
    status: article.status || 'draft',
    seoTitle: article.seo?.title || '',
    seoDescription: article.seo?.description || '',
    isSponsored: !!article.isSponsored,
  }
}

export default function AdminArticleEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [authors, setAuthors] = useState([])
  const [topics, setTopics] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchAuthors(), fetchTopics(), isNew ? Promise.resolve(null) : fetchArticleBySlug(id)])
      .then(([authorList, topicList, existing]) => {
        if (!active) return
        setAuthors(authorList)
        setTopics(topicList)
        if (isNew) {
          setForm(blankForm(authorList[0]?.slug))
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the article editor. Please try again.'))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isNew])

  function updateField(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'title' && !slugTouched) {
        next.slug = slugify(value)
      }
      return next
    })
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as an article slug.`
    return null
  }

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
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

    const payload = {
      title: form.title,
      slug: form.slug,
      subtitle: form.subtitle || null,
      excerpt: form.excerpt || null,
      authorSlug: form.authorSlug,
      topicSlugs: form.topicSlugs,
      status: nextStatus,
      isSponsored: form.isSponsored,
      seo: { title: form.seoTitle || null, description: form.seoDescription || null },
    }

    try {
      const saved = isNew ? await createArticle(payload) : await updateArticle(id, payload)
      toast.success(`Article ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus.replace('_', ' ')}.`)
      if (isNew) navigate(`/admin/articles/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong saving this article. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the article editor" description={loadError} />
  if (notFound) return <EmptyState title="Article not found" description="This article may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Article' : `Edit: ${form.title || 'Untitled'}`}
        description="Public URL is flat — never /articles/{slug}."
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && (
              <a href={`/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4 border border-taupe-200 bg-white p-6">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Title</label>
            <input value={form.title} onChange={(e) => updateField('title', e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Slug <span className="normal-case text-charcoal-600/60">— public URL: womenshapingfutures.org/{form.slug || 'your-slug'}</span>
            </label>
            <input
              value={form.slug}
              onChange={(e) => {
                setSlugTouched(true)
                updateField('slug', slugify(e.target.value))
              }}
              className={`mt-1.5 w-full border px-3 py-2.5 text-sm focus:outline-none ${errors.slug ? 'border-rose-500' : 'border-taupe-300 focus:border-burgundy-500'}`}
            />
            {errors.slug && <p className="mt-1 text-xs text-rose-600">{errors.slug}</p>}
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Subtitle / Dek</label>
            <input value={form.subtitle} onChange={(e) => updateField('subtitle', e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Excerpt</label>
            <textarea rows={2} value={form.excerpt} onChange={(e) => updateField('excerpt', e.target.value)} className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              Hero image (media path) <span className="normal-case text-charcoal-600/60">— upload handled by Media Library</span>
            </label>
            <input value={form.heroImage} onChange={(e) => updateField('heroImage', e.target.value)} placeholder="articles/my-hero-image" className="mt-1.5 w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>

          <div className="border-t border-taupe-200 pt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">SEO</p>
            <div className="mt-2 space-y-3">
              <input placeholder="SEO title" value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              <textarea placeholder="Meta description" rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Status</p>
            <select value={form.status} onChange={(e) => updateField('status', e.target.value)} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace('_', ' ')}
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
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Author</p>
            <select value={form.authorSlug} onChange={(e) => updateField('authorSlug', e.target.value)} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm">
              {authors.map((a) => (
                <option key={a.slug} value={a.slug}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Topics</p>
            <div className="mt-2 flex flex-wrap gap-2">
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
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.isSponsored} onChange={(e) => updateField('isSponsored', e.target.checked)} />
              Sponsored content
            </label>
          </div>

          <Link to="/admin/articles" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all articles
          </Link>
        </div>
      </div>
    </div>
  )
}
