import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, Archive, Trash2, ChevronUp, ChevronDown, Plus, Users } from 'lucide-react'
import {
  fetchAdminLearningProgram,
  createAdminLearningProgram,
  updateAdminLearningProgram,
  updateAdminLearningCurriculum,
} from '../../api/learning'
import { fetchArticles } from '../../api/articles'
import { fetchResources } from '../../api/resources'
import { fetchEvents } from '../../api/events'
import { fetchProducts } from '../../api/products'
import { fetchAuthors, fetchOrganizations, fetchTopics } from '../../api/taxonomies'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import MediaPicker from '../../components/cms/MediaPicker'
import ArticleBlockEditor from '../../components/cms/ArticleBlockEditor'
import EntitySelect from '../../components/cms/EntitySelect'
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

const STATUSES = ['draft', 'review', 'published', 'archived']
const PROGRAM_TYPES = [
  { value: 'course', label: 'Course' },
  { value: 'masterclass', label: 'Masterclass' },
  { value: 'program', label: 'Program' },
  { value: 'learning_series', label: 'Learning Series' },
]
const DIFFICULTY_LEVELS = ['beginner', 'intermediate', 'advanced', 'all_levels']
const AUDIENCE_TYPES = ['aspiring_leaders', 'professionals', 'entrepreneurs', 'founders', 'career_changers', 'students', 'general']
const DURATION_UNITS = ['minutes', 'hours', 'days', 'weeks']
const DELIVERY_MODES = [
  { value: 'self_paced', label: 'Self-paced' },
  { value: 'live_online', label: 'Live online' },
  { value: 'in_person', label: 'In person' },
  { value: 'hybrid', label: 'Hybrid' },
]
const ACCESS_TYPES = [
  { value: 'free', label: 'Free — publicly accessible, no login or checkout' },
  { value: 'external', label: 'External — sends visitors to a safe external enrollment URL' },
  { value: 'product', label: 'Product — linked to an existing Product for commercial access' },
]
const LESSON_TYPES = [
  { value: 'text', label: 'Text' },
  { value: 'article', label: 'Article' },
  { value: 'resource', label: 'Resource' },
  { value: 'video', label: 'Video (external link)' },
  { value: 'external_link', label: 'External link' },
  { value: 'activity', label: 'Activity' },
]

async function searchAuthors(query) {
  const res = await fetchAuthors({ query, pageSize: 8 })
  return res.items.map((a) => ({ value: a.slug, label: a.name, sublabel: a.role || undefined }))
}
async function searchOrganizations(query) {
  const res = await fetchOrganizations({ query, pageSize: 8 })
  return res.items.map((o) => ({ value: o.slug, label: o.name }))
}
async function searchProducts(query) {
  const res = await fetchProducts({ query, pageSize: 8 })
  return res.items.map((p) => ({ value: p.slug, label: p.name }))
}
async function searchEvents(query) {
  const res = await fetchEvents({ query, pageSize: 8 })
  return res.items.map((e) => ({ value: e.slug, label: e.title, sublabel: e.date || undefined }))
}
async function searchArticles(query) {
  const res = await fetchArticles({ query, pageSize: 8 })
  return res.items.map((a) => ({ value: a.slug, label: a.title }))
}
async function searchResources(query) {
  const res = await fetchResources({ q: query, pageSize: 8 })
  return res.items.map((r) => ({ value: r.slug, label: r.name }))
}
async function searchTopics(query) {
  const all = await fetchTopics()
  const q = (query || '').toLowerCase()
  return all.filter((t) => !q || t.name.toLowerCase().includes(q)).slice(0, 12).map((t) => ({ value: t.slug, label: t.name }))
}

function blankForm() {
  return {
    title: '',
    slug: '',
    subtitle: '',
    shortDescription: '',
    programType: 'course',
    difficultyLevel: '',
    audience: [],
    topicSlugs: [],
    overview: [],
    learningOutcomes: [],
    prerequisites: [],
    durationValue: '',
    durationUnit: '',
    heroMedia: null,
    primaryInstructorSlug: null,
    coInstructorSlugs: [],
    providerOrganizationSlug: null,
    deliveryMode: 'self_paced',
    eventSlugs: [],
    accessType: 'free',
    productSlug: null,
    externalUrl: '',
    relatedArticleSlugs: [],
    relatedResourceSlugs: [],
    featured: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(p) {
  return {
    title: p.title || '',
    slug: p.slug || '',
    subtitle: p.subtitle || '',
    shortDescription: p.shortDescription || '',
    programType: p.programType || 'course',
    difficultyLevel: p.difficultyLevel || '',
    audience: p.audience || [],
    topicSlugs: (p.topics || []).map((t) => t.slug),
    overview: p.overview || [],
    learningOutcomes: p.learningOutcomes || [],
    prerequisites: p.prerequisites || [],
    durationValue: p.durationValue ?? '',
    durationUnit: p.durationUnit || '',
    heroMedia: p.heroMedia || null,
    primaryInstructorSlug: p.primaryInstructor?.slug || null,
    coInstructorSlugs: (p.coInstructors || []).map((i) => i.slug),
    providerOrganizationSlug: p.providerOrganization?.slug || null,
    deliveryMode: p.deliveryMode || 'self_paced',
    eventSlugs: (p.events || []).map((e) => e.slug),
    accessType: p.accessType || 'free',
    productSlug: p.product?.slug || null,
    externalUrl: p.externalUrl || '',
    relatedArticleSlugs: (p.relatedArticles || []).map((a) => a.slug),
    relatedResourceSlugs: (p.relatedResources || []).map((r) => r.slug),
    featured: !!p.featured,
    status: p.status || 'draft',
    seoTitle: p.seo?.title || '',
    seoDescription: p.seo?.description || '',
    seoCanonical: p.seo?.canonical || '',
    seoOgMedia: p.seo?.ogImageMediaId ? { id: p.seo.ogImageMediaId } : null,
  }
}

function modulesToForm(p) {
  return (p.modules || []).map((m) => ({
    id: m.id,
    title: m.title,
    description: m.description || '',
    lessons: (m.lessons || []).map((l) => ({
      id: l.id,
      title: l.title,
      lessonType: l.lessonType || 'text',
      summary: l.summary || '',
      content: l.content || [],
      articleSlug: l.article?.slug || null,
      resourceSlug: l.resource?.slug || null,
      externalUrl: l.externalUrl || '',
      durationMinutes: l.durationMinutes ?? '',
    })),
  }))
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

function ItemShell({ label, onMoveUp, onMoveDown, onRemove, canMoveUp, canMoveDown, children }) {
  return (
    <div className="border border-taupe-200 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/70">{label}</span>
        <div className="flex items-center gap-1">
          <button type="button" onClick={onMoveUp} disabled={!canMoveUp} aria-label="Move up" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronUp size={15} />
          </button>
          <button type="button" onClick={onMoveDown} disabled={!canMoveDown} aria-label="Move down" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronDown size={15} />
          </button>
          <button type="button" onClick={onRemove} aria-label="Remove" className="p-1 text-charcoal-600 hover:text-rose-600">
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      {children}
    </div>
  )
}

const inputClass = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

function LessonEditor({ lesson, onChange, onRemove, onMoveUp, onMoveDown, canMoveUp, canMoveDown }) {
  function patch(fields) {
    onChange({ ...lesson, ...fields })
  }
  return (
    <ItemShell label={`Lesson: ${lesson.title || 'Untitled'}`} onMoveUp={onMoveUp} onMoveDown={onMoveDown} onRemove={onRemove} canMoveUp={canMoveUp} canMoveDown={canMoveDown}>
      <div className="space-y-2">
        <input value={lesson.title} onChange={(e) => patch({ title: e.target.value })} placeholder="Lesson title" className={inputClass} />
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <select value={lesson.lessonType} onChange={(e) => patch({ lessonType: e.target.value })} className={inputClass}>
            {LESSON_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <input
            type="number"
            min="0"
            value={lesson.durationMinutes}
            onChange={(e) => patch({ durationMinutes: e.target.value })}
            placeholder="Duration (minutes, optional)"
            className={inputClass}
          />
        </div>
        <input value={lesson.summary} onChange={(e) => patch({ summary: e.target.value })} placeholder="Short summary (optional)" className={inputClass} />

        {lesson.lessonType === 'article' && (
          <EntitySelect value={lesson.articleSlug} onChange={(v) => patch({ articleSlug: v })} loadOptions={searchArticles} placeholder="Search articles to link…" />
        )}
        {lesson.lessonType === 'resource' && (
          <EntitySelect value={lesson.resourceSlug} onChange={(v) => patch({ resourceSlug: v })} loadOptions={searchResources} placeholder="Search resources to link…" />
        )}
        {(lesson.lessonType === 'video' || lesson.lessonType === 'external_link') && (
          <input value={lesson.externalUrl} onChange={(e) => patch({ externalUrl: e.target.value })} placeholder="https://…" className={inputClass} />
        )}
        {(lesson.lessonType === 'text' || lesson.lessonType === 'activity') && (
          <div className="border border-taupe-200 p-2">
            <ArticleBlockEditor blocks={lesson.content} onChange={(v) => patch({ content: v })} />
          </div>
        )}
      </div>
    </ItemShell>
  )
}

function ModuleEditor({ module, onChange, onRemove, onMoveUp, onMoveDown, canMoveUp, canMoveDown }) {
  function patch(fields) {
    onChange({ ...module, ...fields })
  }
  function addLesson() {
    patch({ lessons: [...module.lessons, { title: '', lessonType: 'text', summary: '', content: [], articleSlug: null, resourceSlug: null, externalUrl: '', durationMinutes: '' }] })
  }
  function updateLessonAt(i, next) {
    patch({ lessons: module.lessons.map((l, idx) => (idx === i ? next : l)) })
  }
  function removeLessonAt(i) {
    patch({ lessons: module.lessons.filter((_, idx) => idx !== i) })
  }
  function moveLessonAt(i, dir) {
    const target = i + dir
    if (target < 0 || target >= module.lessons.length) return
    const next = [...module.lessons]
    ;[next[i], next[target]] = [next[target], next[i]]
    patch({ lessons: next })
  }

  return (
    <div className="border border-taupe-300 bg-blush-50/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Module</span>
        <div className="flex items-center gap-1">
          <button type="button" onClick={onMoveUp} disabled={!canMoveUp} aria-label="Move module up" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronUp size={15} />
          </button>
          <button type="button" onClick={onMoveDown} disabled={!canMoveDown} aria-label="Move module down" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronDown size={15} />
          </button>
          <button type="button" onClick={onRemove} aria-label="Remove module" className="p-1 text-charcoal-600 hover:text-rose-600">
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      <div className="space-y-2">
        <input value={module.title} onChange={(e) => patch({ title: e.target.value })} placeholder="Module title" className={inputClass} />
        <textarea rows={2} value={module.description} onChange={(e) => patch({ description: e.target.value })} placeholder="Module description (optional)" className={inputClass} />
      </div>
      <div className="mt-3 space-y-3">
        {module.lessons.map((lesson, i) => (
          <LessonEditor
            key={i}
            lesson={lesson}
            onChange={(next) => updateLessonAt(i, next)}
            onRemove={() => removeLessonAt(i)}
            onMoveUp={() => moveLessonAt(i, -1)}
            onMoveDown={() => moveLessonAt(i, 1)}
            canMoveUp={i > 0}
            canMoveDown={i < module.lessons.length - 1}
          />
        ))}
      </div>
      <button type="button" onClick={addLesson} className="btn-secondary mt-3 !px-3 !py-1.5 text-xs">
        <Plus size={13} /> Add lesson
      </button>
    </div>
  )
}

function CurriculumEditor({ programId, initialModules }) {
  const [modules, setModules] = useState(initialModules)
  const [saving, setSaving] = useState(false)

  function addModule() {
    setModules([...modules, { title: '', description: '', lessons: [] }])
  }
  function updateAt(i, next) {
    setModules(modules.map((m, idx) => (idx === i ? next : m)))
  }
  function removeAt(i) {
    setModules(modules.filter((_, idx) => idx !== i))
  }
  function moveAt(i, dir) {
    const target = i + dir
    if (target < 0 || target >= modules.length) return
    const next = [...modules]
    ;[next[i], next[target]] = [next[target], next[i]]
    setModules(next)
  }

  async function handleSaveCurriculum() {
    setSaving(true)
    try {
      const saved = await updateAdminLearningCurriculum(programId, modules)
      setModules(modulesToForm(saved))
      toast.success('Curriculum saved.')
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving the curriculum.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Section title="Curriculum" description="Modules and lessons — a lesson references an existing Article or Resource, or carries its own text/video link. Saving here replaces the whole curriculum atomically.">
      <div className="space-y-4">
        {modules.map((module, i) => (
          <ModuleEditor
            key={i}
            module={module}
            onChange={(next) => updateAt(i, next)}
            onRemove={() => removeAt(i)}
            onMoveUp={() => moveAt(i, -1)}
            onMoveDown={() => moveAt(i, 1)}
            canMoveUp={i > 0}
            canMoveDown={i < modules.length - 1}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={addModule} className="btn-secondary !px-3 !py-1.5 text-xs">
          <Plus size={13} /> Add module
        </button>
        <button type="button" onClick={handleSaveCurriculum} disabled={saving} className="btn-primary !px-3 !py-1.5 text-xs disabled:opacity-60">
          <Save size={13} /> {saving ? 'Saving curriculum…' : 'Save curriculum'}
        </button>
      </div>
    </Section>
  )
}

export default function AdminLearningProgramEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [form, setForm] = useState(undefined)
  const [modules, setModules] = useState([])
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    if (isNew) {
      setForm(blankForm())
      return
    }
    fetchAdminLearningProgram(id)
      .then((existing) => {
        if (!active) return
        if (existing) {
          setForm(toForm(existing))
          setModules(modulesToForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the Learning editor. Please try again.'))
    return () => {
      active = false
    }
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

  function toggleAudience(value) {
    setForm((prev) => ({
      ...prev,
      audience: prev.audience.includes(value) ? prev.audience.filter((a) => a !== value) : [...prev.audience, value],
    }))
  }

  const hasNoInstructor = form && !form.primaryInstructorSlug
  const productWithoutSlug = form && form.accessType === 'product' && !form.productSlug
  const externalWithoutUrl = form && form.accessType === 'external' && !form.externalUrl

  async function handleSave(nextStatus) {
    if (!form.title) {
      toast.error('Give this program a title.')
      return
    }
    if (nextStatus === 'published') {
      if (hasNoInstructor) {
        toast.error('An instructor is required before publishing.')
        return
      }
      if (productWithoutSlug) {
        toast.error('A "product" access program must be linked to a Product before publishing.')
        return
      }
      if (externalWithoutUrl) {
        toast.error('An "external" access program needs an external URL before publishing.')
        return
      }
    }
    setErrors({})
    setSaving(true)

    const payload = {
      title: form.title,
      slug: form.slug || undefined,
      subtitle: form.subtitle || undefined,
      shortDescription: form.shortDescription || undefined,
      programType: form.programType,
      difficultyLevel: form.difficultyLevel || undefined,
      audience: form.audience,
      topicSlugs: form.topicSlugs,
      overview: form.overview,
      learningOutcomes: form.learningOutcomes,
      prerequisites: form.prerequisites,
      durationValue: form.durationValue === '' ? undefined : Number(form.durationValue),
      durationUnit: form.durationUnit || undefined,
      heroMediaId: form.heroMedia?.id || undefined,
      primaryInstructorSlug: form.primaryInstructorSlug || undefined,
      coInstructorSlugs: form.coInstructorSlugs,
      providerOrganizationSlug: form.providerOrganizationSlug || undefined,
      deliveryMode: form.deliveryMode,
      eventSlugs: form.eventSlugs,
      accessType: form.accessType,
      productSlug: form.accessType === 'product' ? form.productSlug || undefined : undefined,
      externalUrl: form.accessType === 'external' ? form.externalUrl || undefined : undefined,
      relatedArticleSlugs: form.relatedArticleSlugs,
      relatedResourceSlugs: form.relatedResourceSlugs,
      featured: form.featured,
      status: nextStatus,
      seo: {
        title: form.seoTitle || undefined,
        description: form.seoDescription || undefined,
        canonical: form.seoCanonical || undefined,
        ogImageMediaId: form.seoOgMedia?.id || undefined,
      },
    }

    try {
      const saved = isNew ? await createAdminLearningProgram(payload) : await updateAdminLearningProgram(id, payload)
      toast.success(`Learning program ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/learning/${saved.id}`)
      else {
        setForm(toForm(saved))
        setModules(modulesToForm(saved))
      }
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this program. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the Learning editor" description={loadError} />
  if (notFound) return <EmptyState title="Learning program not found" description="This program may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Learning Program' : `Edit: ${form.title || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/learning/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.accessType === 'free' && (
              <Link to={`/admin/learning/${id}/enrollments`} className="btn-secondary !px-4 !py-2 text-xs">
                <Users size={14} /> Enrollments
              </Link>
            )}
            {!isNew && form.slug && (
              <a href={`/learning/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
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
              <input value={form.title} onChange={(e) => updateField('title', e.target.value)} className={inputClass} />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/learning/${form.slug || 'your-slug'}`}>
              <input
                value={form.slug}
                onChange={(e) => {
                  setSlugTouched(true)
                  updateField('slug', slugify(e.target.value))
                }}
                className={`${inputClass} ${errors.slug ? 'border-rose-500' : ''}`}
              />
            </Field>
            <Field label="Subtitle" hint="optional">
              <input value={form.subtitle} onChange={(e) => updateField('subtitle', e.target.value)} className={inputClass} />
            </Field>
            <Field label="Short description" hint="shown on program cards">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className={inputClass} />
            </Field>
            <Field label="Program type">
              <select value={form.programType} onChange={(e) => updateField('programType', e.target.value)} className={inputClass}>
                {PROGRAM_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </Field>
          </Section>

          <Section title="Overview" description="Structure the content however makes sense — you decide the headings.">
            <ArticleBlockEditor blocks={form.overview} onChange={(v) => updateField('overview', v)} />
          </Section>

          <Section title="Educational details">
            <Field label="Difficulty level">
              <select value={form.difficultyLevel} onChange={(e) => updateField('difficultyLevel', e.target.value)} className={inputClass}>
                <option value="">— None —</option>
                {DIFFICULTY_LEVELS.map((d) => (
                  <option key={d} value={d}>{d.replace('_', ' ')}</option>
                ))}
              </select>
            </Field>
            <Field label="Audience">
              <div className="flex flex-wrap gap-3">
                {AUDIENCE_TYPES.map((a) => (
                  <label key={a} className="flex items-center gap-1.5 text-sm text-charcoal-600">
                    <input type="checkbox" checked={form.audience.includes(a)} onChange={() => toggleAudience(a)} />
                    {a.replace('_', ' ')}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="Topics">
              <EntitySelect multiple value={form.topicSlugs} onChange={(v) => updateField('topicSlugs', v)} loadOptions={searchTopics} placeholder="Add a topic…" />
            </Field>
            <Field label="Learning outcomes" hint="one per line">
              <textarea
                rows={3}
                value={form.learningOutcomes.join('\n')}
                onChange={(e) => updateField('learningOutcomes', e.target.value.split('\n').map((s) => s.trim()).filter(Boolean))}
                className={inputClass}
              />
            </Field>
            <Field label="Prerequisites" hint="one per line, optional — never fabricated">
              <textarea
                rows={2}
                value={form.prerequisites.join('\n')}
                onChange={(e) => updateField('prerequisites', e.target.value.split('\n').map((s) => s.trim()).filter(Boolean))}
                className={inputClass}
              />
            </Field>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Field label="Duration" hint="optional">
                <input type="number" min="1" value={form.durationValue} onChange={(e) => updateField('durationValue', e.target.value)} className={inputClass} />
              </Field>
              <Field label="Duration unit">
                <select value={form.durationUnit} onChange={(e) => updateField('durationUnit', e.target.value)} className={inputClass}>
                  <option value="">— None —</option>
                  {DURATION_UNITS.map((u) => (
                    <option key={u} value={u}>{u}</option>
                  ))}
                </select>
              </Field>
            </div>
          </Section>

          <Section title="Instructors" description="Reuses Author — the existing public byline/contributor identity.">
            <Field label="Primary instructor">
              <EntitySelect value={form.primaryInstructorSlug} onChange={(v) => updateField('primaryInstructorSlug', v)} loadOptions={searchAuthors} placeholder="Search authors…" />
            </Field>
            {hasNoInstructor && <p className="text-xs text-amber-700">An instructor is required before publishing.</p>}
            <Field label="Co-instructors" hint="optional">
              <EntitySelect multiple value={form.coInstructorSlugs} onChange={(v) => updateField('coInstructorSlugs', v)} loadOptions={searchAuthors} placeholder="Add a co-instructor…" />
            </Field>
            <Field label="Provider organization" hint="optional — a partner Organization; leave blank for WSF as provider">
              <EntitySelect value={form.providerOrganizationSlug} onChange={(v) => updateField('providerOrganizationSlug', v)} loadOptions={searchOrganizations} placeholder="Search organizations…" />
            </Field>
          </Section>

          <Section title="Delivery" description="Live/cohort sessions are represented via linked Events — no duplicated dates here.">
            <Field label="Delivery mode">
              <select value={form.deliveryMode} onChange={(e) => updateField('deliveryMode', e.target.value)} className={inputClass}>
                {DELIVERY_MODES.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Linked events" hint="upcoming live sessions / cohorts">
              <EntitySelect multiple value={form.eventSlugs} onChange={(v) => updateField('eventSlugs', v)} loadOptions={searchEvents} placeholder="Add an event…" />
            </Field>
          </Section>

          {!isNew && <CurriculumEditor programId={id} initialModules={modules} />}
          {isNew && (
            <Section title="Curriculum">
              <p className="text-sm text-charcoal-600/70">Save this program as a draft first to start adding modules and lessons.</p>
            </Section>
          )}

          <Section title="Access">
            <Field label="Access type">
              <select value={form.accessType} onChange={(e) => updateField('accessType', e.target.value)} className={inputClass}>
                {ACCESS_TYPES.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
            </Field>
            {form.accessType === 'product' && (
              <>
                <Field label="Linked product" hint="Product remains the source of truth for pricing">
                  <EntitySelect value={form.productSlug} onChange={(v) => updateField('productSlug', v)} loadOptions={searchProducts} placeholder="Search products…" />
                </Field>
                {productWithoutSlug && <p className="text-xs text-amber-700">A Product must be linked before publishing.</p>}
              </>
            )}
            {form.accessType === 'external' && (
              <>
                <Field label="External enrollment URL">
                  <input value={form.externalUrl} onChange={(e) => updateField('externalUrl', e.target.value)} placeholder="https://…" className={inputClass} />
                </Field>
                {externalWithoutUrl && <p className="text-xs text-amber-700">An external URL is required before publishing.</p>}
              </>
            )}
          </Section>

          <Section title="Media">
            <MediaPicker label="Hero image" aspect={4 / 3} value={form.heroMedia} onChange={(media) => updateField('heroMedia', media)} />
          </Section>

          <Section title="Related content" description="Link relevant Articles/Resources — never auto-related.">
            <Field label="Related articles">
              <EntitySelect multiple value={form.relatedArticleSlugs} onChange={(v) => updateField('relatedArticleSlugs', v)} loadOptions={searchArticles} placeholder="Add a related article…" />
            </Field>
            <Field label="Related resources">
              <EntitySelect multiple value={form.relatedResourceSlugs} onChange={(v) => updateField('relatedResourceSlugs', v)} loadOptions={searchResources} placeholder="Add a related resource…" />
            </Field>
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the program title">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className={inputClass} />
            </Field>
            <Field label="Meta description" hint="falls back to the short description">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className={inputClass} />
            </Field>
            <Field label="Canonical URL" hint="only set this if republished from elsewhere">
              <input value={form.seoCanonical} onChange={(e) => updateField('seoCanonical', e.target.value)} placeholder="https://…" className={inputClass} />
            </Field>
            <MediaPicker label="Social / OG image" aspect={1.91 / 1} value={form.seoOgMedia} onChange={(media) => updateField('seoOgMedia', media)} />
          </Section>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
            <select value={form.status} onChange={(e) => updateField('status', e.target.value)} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm">
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
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
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
              Featured
            </label>
          </div>

          <Link to="/admin/learning" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all learning programs
          </Link>
        </div>
      </div>
    </div>
  )
}
