import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, AlertTriangle, X } from 'lucide-react'
import { fetchArticleBySlug, createArticle, updateArticle } from '../../api/articles'
import { fetchAuthors, fetchTopics, fetchCategories, fetchSeries } from '../../api/taxonomies'
import { fetchPeople } from '../../api/people'
import { RESERVED_SLUGS } from '../../constants/routes'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import MediaPicker from '../../components/cms/MediaPicker'
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

const STATUSES = ['draft', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published', 'archived']

const AI_INVOLVEMENT_OPTIONS = [
  { value: 'none', label: 'None — no AI involvement' },
  { value: 'ai_assisted', label: 'AI-assisted (research, editing help; a human wrote/owns the piece)' },
  { value: 'ai_generated_reviewed', label: 'AI-generated draft, substantially rewritten/reviewed by a human' },
]

function toDatetimeLocalValue(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function blankForm(defaultAuthorSlug) {
  return {
    title: '',
    slug: '',
    subtitle: '',
    excerpt: '',
    content: [],
    heroMedia: null,
    authorSlug: defaultAuthorSlug || '',
    categorySlug: '',
    topicSlugs: [],
    seriesSlug: '',
    tagSlugs: [],
    relatedPersonSlugs: [],
    status: 'draft',
    featured: false,
    promoted: false,
    isSponsored: false,
    sponsorName: '',
    sponsorDisclosure: '',
    publishDate: '',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
    aiInvolvement: 'none',
    humanReviewed: false,
    aiDisclosureRequired: false,
    aiDisclosureText: '',
    aiEditorialNotes: '',
  }
}

function toForm(article) {
  return {
    title: article.title || '',
    slug: article.slug || '',
    subtitle: article.subtitle || '',
    excerpt: article.excerpt || '',
    content: article.content || [],
    heroMedia: article.heroMediaId
      ? { id: article.heroMediaId, mediaPath: article.heroImage, altText: article.heroImageAlt, caption: article.heroImageCaption, credit: article.heroImageCredit }
      : null,
    authorSlug: article.authorSlug || article.author?.slug || '',
    categorySlug: article.categorySlug || '',
    topicSlugs: article.topicSlugs || [],
    seriesSlug: article.seriesSlug || '',
    tagSlugs: article.tagSlugs || [],
    relatedPersonSlugs: article.relatedPersonSlugs || [],
    status: article.status || 'draft',
    featured: !!article.featured,
    promoted: !!article.promoted,
    isSponsored: !!article.isSponsored,
    sponsorName: article.sponsor?.name || '',
    sponsorDisclosure: article.sponsor?.disclosure || '',
    publishDate: toDatetimeLocalValue(article.publishDate),
    seoTitle: article.seo?.title || '',
    seoDescription: article.seo?.description || '',
    seoCanonical: article.seo?.canonical || '',
    seoOgMedia: article.seo?.ogImageMediaId ? { id: article.seo.ogImageMediaId } : null,
    aiInvolvement: article.aiInvolvement || 'none',
    humanReviewed: !!article.humanReviewed,
    aiDisclosureRequired: !!article.aiDisclosureRequired,
    aiDisclosureText: article.aiDisclosureText || '',
    aiEditorialNotes: article.aiEditorialNotes || '',
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

export default function AdminArticleEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [authors, setAuthors] = useState([])
  const [topics, setTopics] = useState([])
  const [categories, setCategories] = useState([])
  const [series, setSeries] = useState([])
  const [people, setPeople] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([
      // Only active authors are offered for new assignments; an existing
      // article's already-assigned author is preserved below even if they
      // later became archived — a historical byline must never break.
      fetchAuthors({ status: 'active', pageSize: 200 }),
      fetchTopics(),
      fetchCategories(),
      fetchSeries(),
      fetchPeople({ pageSize: 200 }),
      isNew ? Promise.resolve(null) : fetchArticleBySlug(id),
    ])
      .then(([authorRes, topicList, categoryList, seriesList, peopleRes, existing]) => {
        if (!active) return
        let authorList = authorRes.items
        if (existing?.authorSlug && !authorList.some((a) => a.slug === existing.authorSlug)) {
          authorList = [...authorList, { slug: existing.authorSlug, name: `${existing.author?.name || existing.authorSlug} (inactive)`, role: existing.author?.role }]
        }
        setAuthors(authorList)
        setTopics(topicList)
        setCategories(categoryList)
        setSeries(seriesList)
        setPeople(peopleRes.items)
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

  function toggleInList(field, slug) {
    setForm((prev) => ({
      ...prev,
      [field]: prev[field].includes(slug) ? prev[field].filter((s) => s !== slug) : [...prev[field], slug],
    }))
  }

  const needsAiReviewConfirmation = form && form.aiInvolvement !== 'none' && !form.humanReviewed
  const hasNoContent = form && form.content.length === 0

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (nextStatus === 'published') {
      if (hasNoContent) {
        toast.error('Article body is required before publishing. Add at least one block in the Content section.')
        return
      }
      if (needsAiReviewConfirmation) {
        toast.error('This article is marked AI-assisted/AI-generated and must be confirmed as human-reviewed before it can be published.')
        return
      }
    }
    setErrors({})
    setSaving(true)

    const payload = {
      title: form.title,
      slug: form.slug,
      subtitle: form.subtitle || null,
      excerpt: form.excerpt || null,
      heroMediaId: form.heroMedia?.id || null,
      heroImageCaption: form.heroMedia?.caption || null,
      heroImageCredit: form.heroMedia?.credit || null,
      authorSlug: form.authorSlug,
      categorySlug: form.categorySlug || null,
      topicSlugs: form.topicSlugs,
      seriesSlug: form.seriesSlug || null,
      tagSlugs: form.tagSlugs,
      relatedPersonSlugs: form.relatedPersonSlugs,
      status: nextStatus,
      featured: form.featured,
      promoted: form.promoted,
      isSponsored: form.isSponsored,
      sponsor: form.isSponsored ? { name: form.sponsorName || null, disclosure: form.sponsorDisclosure || null } : null,
      publishDate: form.publishDate ? new Date(form.publishDate).toISOString() : null,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
      content: form.content,
      aiInvolvement: form.aiInvolvement,
      humanReviewed: form.humanReviewed,
      aiDisclosureRequired: form.aiDisclosureRequired,
      aiDisclosureText: form.aiDisclosureText || null,
      aiEditorialNotes: form.aiEditorialNotes || null,
    }

    try {
      const saved = isNew ? await createArticle(payload) : await updateArticle(id, payload)
      toast.success(`Article ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus.replace('_', ' ')}.`)
      if (isNew) navigate(`/admin/articles/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this article. Please try again.'
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Title">
              <input value={form.title} onChange={(e) => updateField('title', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/${form.slug || 'your-slug'}`}>
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
            <Field label="Subtitle / Deck">
              <input value={form.subtitle} onChange={(e) => updateField('subtitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Excerpt">
              <textarea rows={2} value={form.excerpt} onChange={(e) => updateField('excerpt', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Content" description="Write the full article body here — this is what publishes to the public page.">
            <ArticleBlockEditor blocks={form.content} onChange={(content) => updateField('content', content)} />
          </Section>

          <Section title="Media" description="The hero image leads the article and its cards across the site.">
            <MediaPicker label="Hero image" aspect={16 / 9} value={form.heroMedia} onChange={(media) => updateField('heroMedia', media)} />
            {form.heroMedia && (
              <div className="space-y-2">
                <Field label="Hero alt text" hint="edit in Media Library">
                  <input value={form.heroMedia.altText || ''} disabled className="w-full border border-taupe-200 bg-taupe-100/60 px-3 py-2 text-xs text-charcoal-600" />
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Caption">
                    <input
                      value={form.heroMedia.caption || ''}
                      onChange={(e) => updateField('heroMedia', { ...form.heroMedia, caption: e.target.value })}
                      className="w-full border border-taupe-300 px-3 py-2 text-xs focus:border-burgundy-500 focus:outline-none"
                    />
                  </Field>
                  <Field label="Credit">
                    <input
                      value={form.heroMedia.credit || ''}
                      onChange={(e) => updateField('heroMedia', { ...form.heroMedia, credit: e.target.value })}
                      className="w-full border border-taupe-300 px-3 py-2 text-xs focus:border-burgundy-500 focus:outline-none"
                    />
                  </Field>
                </div>
              </div>
            )}
          </Section>

          <Section title="Classification">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Author">
                <select value={form.authorSlug} onChange={(e) => updateField('authorSlug', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  {authors.map((a) => (
                    <option key={a.slug} value={a.slug}>
                      {a.name}
                      {a.role ? ` — ${a.role}` : ''}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Category" hint="optional">
                <select value={form.categorySlug} onChange={(e) => updateField('categorySlug', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {categories.map((c) => (
                    <option key={c.slug} value={c.slug}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Series" hint="optional">
              <select value={form.seriesSlug} onChange={(e) => updateField('seriesSlug', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {series.map((s) => (
                  <option key={s.slug} value={s.slug}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Topics">
              <div className="flex flex-wrap gap-2">
                {topics.map((t) => (
                  <button
                    key={t.slug}
                    type="button"
                    onClick={() => toggleInList('topicSlugs', t.slug)}
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
            <Field label="People mentioned / profiled" hint="optional">
              <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto">
                {people.map((p) => (
                  <button
                    key={p.slug}
                    type="button"
                    onClick={() => toggleInList('relatedPersonSlugs', p.slug)}
                    className={`px-2.5 py-1 text-xs font-medium ${form.relatedPersonSlugs.includes(p.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </Field>
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the article title">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the excerpt">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint="only set this if the story is republished from elsewhere">
              <input value={form.seoCanonical} onChange={(e) => updateField('seoCanonical', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <MediaPicker label="Social / OG image" aspect={1.91 / 1} value={form.seoOgMedia} onChange={(media) => updateField('seoOgMedia', media)} />
          </Section>
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
            <Field label="Scheduled / publish date" hint="optional">
              <input
                type="datetime-local"
                value={form.publishDate}
                onChange={(e) => updateField('publishDate', e.target.value)}
                className="w-full border border-taupe-300 px-3 py-2 text-sm"
              />
            </Field>
            <div className="mt-3 space-y-2 border-t border-taupe-200 pt-3">
              <label className="flex items-center gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
                Featured
              </label>
              <label className="flex items-center gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.promoted} onChange={(e) => updateField('promoted', e.target.checked)} />
                Promoted
              </label>
              <label className="flex items-center gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.isSponsored} onChange={(e) => updateField('isSponsored', e.target.checked)} />
                Sponsored content
              </label>
              {form.isSponsored && (
                <div className="space-y-2 pl-6">
                  <input
                    value={form.sponsorName}
                    onChange={(e) => updateField('sponsorName', e.target.value)}
                    placeholder="Sponsor name"
                    className="w-full border border-taupe-300 px-3 py-2 text-xs focus:border-burgundy-500 focus:outline-none"
                  />
                  <input
                    value={form.sponsorDisclosure}
                    onChange={(e) => updateField('sponsorDisclosure', e.target.value)}
                    placeholder="Disclosure text"
                    className="w-full border border-taupe-300 px-3 py-2 text-xs focus:border-burgundy-500 focus:outline-none"
                  />
                </div>
              )}
            </div>

            {needsAiReviewConfirmation && (
              <div className="mt-4 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>This article is marked AI-assisted/AI-generated. It can&apos;t be published until it&apos;s confirmed human-reviewed below.</span>
              </div>
            )}
            {hasNoContent && (
              <div className="mt-2 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add content in the Content section before publishing.</span>
              </div>
            )}

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
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">AI / editorial transparency</p>
            <p className="mt-1 text-xs text-charcoal-600/70">
              This is editorial governance, not an AI writer — record how generative AI was used, if at all, and whether a human reviewed it.
            </p>
            <div className="mt-3 space-y-3">
              <Field label="AI involvement">
                <select value={form.aiInvolvement} onChange={(e) => updateField('aiInvolvement', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-xs">
                  {AI_INVOLVEMENT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              <label className="flex items-center gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.humanReviewed} onChange={(e) => updateField('humanReviewed', e.target.checked)} />
                Human-reviewed
              </label>
              <label className="flex items-center gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.aiDisclosureRequired} onChange={(e) => updateField('aiDisclosureRequired', e.target.checked)} />
                Show a public AI disclosure
              </label>
              {form.aiDisclosureRequired && (
                <Field label="Public disclosure text" hint="shown on the article page — keep it short">
                  <textarea
                    rows={2}
                    value={form.aiDisclosureText}
                    onChange={(e) => updateField('aiDisclosureText', e.target.value)}
                    placeholder="This article was created with assistance from generative AI and reviewed by the Women Shaping Futures editorial team."
                    className="w-full border border-taupe-300 px-3 py-2 text-xs focus:border-burgundy-500 focus:outline-none"
                  />
                </Field>
              )}
              <Field label="Internal editorial notes" hint="CMS-only — never shown publicly">
                <textarea
                  rows={2}
                  value={form.aiEditorialNotes}
                  onChange={(e) => updateField('aiEditorialNotes', e.target.value)}
                  placeholder="e.g. drafted with an LLM from the interview transcript, fact-checked against primary sources"
                  className="w-full border border-taupe-300 px-3 py-2 text-xs focus:border-burgundy-500 focus:outline-none"
                />
              </Field>
            </div>
          </div>

          <Link to="/admin/articles" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all articles
          </Link>
        </div>
      </div>
    </div>
  )
}
