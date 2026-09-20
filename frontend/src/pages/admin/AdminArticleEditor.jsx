import { useState, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye } from 'lucide-react'
import { articles } from '../../mock/articles'
import { adminPipelineArticles } from '../../mock/admin'
import { authors } from '../../mock/authors'
import { topics } from '../../mock/topics'
import { RESERVED_SLUGS } from '../../mock'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'

function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

const STATUSES = ['draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published', 'archived']

function findRecord(id) {
  const published = articles.find((a) => a.id === id)
  if (published) {
    return {
      title: published.title,
      slug: published.slug,
      subtitle: published.subtitle,
      excerpt: published.excerpt,
      heroImage: published.heroImage,
      authorSlug: published.authorSlug,
      topicSlugs: published.topicSlugs,
      status: published.status,
      seoTitle: published.seo?.title || '',
      seoDescription: published.seo?.description || '',
      isSponsored: published.isSponsored,
    }
  }
  const pipeline = adminPipelineArticles.find((a) => a.id === id)
  if (pipeline) {
    return {
      title: pipeline.title,
      slug: '',
      subtitle: '',
      excerpt: '',
      heroImage: '',
      authorSlug: pipeline.authorSlug,
      topicSlugs: [pipeline.topicSlug],
      status: pipeline.status,
      seoTitle: '',
      seoDescription: '',
      isSponsored: false,
    }
  }
  return null
}

const blankForm = {
  title: '',
  slug: '',
  subtitle: '',
  excerpt: '',
  heroImage: '',
  authorSlug: authors[0].slug,
  topicSlugs: [],
  status: 'draft',
  seoTitle: '',
  seoDescription: '',
  isSponsored: false,
}

export default function AdminArticleEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id
  const existing = useMemo(() => (id ? findRecord(id) : null), [id])
  const [form, setForm] = useState(existing || blankForm)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})

  const allSlugs = articles.map((a) => a.slug)

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
    if (allSlugs.includes(slug) && slug !== existing?.slug) return 'This slug is already in use by another article.'
    return null
  }

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    setErrors({})
    toast.success(`Article ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus.replace('_', ' ')}.`)
    if (isNew) navigate('/admin/articles')
  }

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
              <button type="button" onClick={() => handleSave('draft')} className="btn-secondary w-full !py-2 text-xs">
                <Save size={13} /> Save draft
              </button>
              <button type="button" onClick={() => handleSave('published')} className="btn-primary w-full !py-2 text-xs">
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
