import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'react-toastify'
import { ChevronDown, ChevronUp, Eye, Save, Trash2, X } from 'lucide-react'
import { fetchAdminLearningPrograms } from '../../api/learning'
import { deleteAdminLearningPath, fetchAdminLearningPath, saveAdminLearningPath } from '../../api/learningPaths'
import { CAREER_GOAL_OPTIONS } from '../../constants/careerMetadata'
import { LEVEL_LABEL } from '../../utils/learning'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ArticleBlockEditor from '../../components/cms/ArticleBlockEditor'
import MediaPicker from '../../components/cms/MediaPicker'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const input = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

function blank() {
  return { title: '', slug: '', subtitle: '', shortDescription: '', description: [], careerGoal: '', difficultyLevel: '', heroMedia: null, status: 'draft', featured: false, seo: { title: '', description: '' }, programs: [] }
}

function Section({ title, description, children }) {
  return (
    <section className="border border-taupe-200 bg-white p-6">
      <h2 className="font-serif text-lg font-semibold text-charcoal">{title}</h2>
      {description && <p className="mt-0.5 text-xs text-charcoal-600/80">{description}</p>}
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  )
}

function Field({ label, children, hint }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
        {label} {hint && <span className="normal-case text-charcoal-600/60">— {hint}</span>}
      </span>
      <span className="mt-1.5 block">{children}</span>
    </label>
  )
}

// Ordered courses: search existing programs, then order them with
// explicit move up/down controls (no drag-and-drop builder).
function ProgramPicker({ programs, onChange }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])

  useEffect(() => {
    if (!query.trim()) return undefined
    let active = true
    const timer = setTimeout(() => {
      fetchAdminLearningPrograms({ query, pageSize: 8 })
        .then((res) => active && setResults(res.items))
        .catch(() => {})
    }, 200)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [query])

  const move = (i, dir) => {
    const target = i + dir
    if (target < 0 || target >= programs.length) return
    const copy = [...programs]
    ;[copy[i], copy[target]] = [copy[target], copy[i]]
    onChange(copy)
  }
  const shown = query.trim() ? results.filter((r) => !programs.some((p) => p.id === r.id)) : []

  return (
    <div className="space-y-3">
      {programs.length > 0 ? (
        <ol className="divide-y divide-taupe-100 border border-taupe-200">
          {programs.map((p, i) => (
            <li key={p.id} className="flex items-center gap-3 px-3 py-2.5">
              <span className="w-6 text-right font-semibold text-charcoal-600">{i + 1}.</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-charcoal">{p.title}</span>
                <span className="text-xs text-charcoal-600">{p.status !== 'published' ? `${p.status} — hidden from the public path until published` : 'published'}</span>
              </span>
              <button type="button" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move ${p.title} up`} className="p-1.5 text-charcoal-600 disabled:opacity-30"><ChevronUp size={15} /></button>
              <button type="button" onClick={() => move(i, 1)} disabled={i === programs.length - 1} aria-label={`Move ${p.title} down`} className="p-1.5 text-charcoal-600 disabled:opacity-30"><ChevronDown size={15} /></button>
              <button type="button" onClick={() => onChange(programs.filter((x) => x.id !== p.id))} aria-label={`Remove ${p.title}`} className="p-1.5 text-charcoal-600 hover:text-rose-600"><X size={15} /></button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-charcoal-600">No courses yet. Search below to add them in order.</p>
      )}
      {programs.length < 12 && (
        <div>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search courses to add…" aria-label="Search courses to add" className={input} />
          {shown.length > 0 && (
            <ul className="mt-1 max-h-48 divide-y divide-taupe-100 overflow-y-auto border border-taupe-200">
              {shown.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => { onChange([...programs, { id: r.id, title: r.title, slug: r.slug, status: r.status }]); setQuery('') }} className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100">
                    {r.title} <span className="text-xs text-charcoal-600">· {r.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default function AdminLearningPathEditor() {
  const { id } = useParams()
  const isNew = !id
  const navigate = useNavigate()
  const [form, setForm] = useState(isNew ? blank() : null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isNew) return undefined
    let active = true
    fetchAdminLearningPath(id)
      .then((p) => active && setForm({ ...blank(), ...p, careerGoal: p.careerGoal || '', difficultyLevel: p.difficultyLevel || '', subtitle: p.subtitle || '', shortDescription: p.shortDescription || '', seo: { title: p.seo?.title || '', description: p.seo?.description || '' } }))
      .catch(() => active && setError('This learning path could not be loaded.'))
    return () => {
      active = false
    }
  }, [id, isNew])

  if (error) return <EmptyState title="Couldn't load the learning path" description={error} />
  if (!form) return <PageLoader />
  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }))

  async function save(status) {
    if (!form.title.trim()) {
      toast.error('Give this learning path a title.')
      return
    }
    setSaving(true)
    try {
      const saved = await saveAdminLearningPath(isNew ? null : id, { ...form, status })
      toast.success(status === 'published' ? 'Learning path published.' : 'Learning path saved.')
      if (isNew) navigate(`/admin/learning/paths/${saved.id}`, { replace: true })
      else setForm((f) => ({ ...f, ...saved, careerGoal: saved.careerGoal || '', difficultyLevel: saved.difficultyLevel || '' }))
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not save this learning path.')
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!window.confirm('Delete this learning path? The courses themselves are not affected.')) return
    try {
      await deleteAdminLearningPath(id)
      toast.success('Learning path deleted.')
      navigate('/admin/learning/paths')
    } catch {
      toast.error('Could not delete this learning path.')
    }
  }

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New learning path' : `Edit: ${form.title || 'Untitled'}`}
        description="A guided journey through existing courses. Only published courses appear publicly."
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.status === 'published' && (
              <a href={`/learning/paths/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> View
              </a>
            )}
          </>
        }
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Title"><input value={form.title} onChange={(e) => update('title', e.target.value)} maxLength={200} className={input} /></Field>
            <Field label="Slug" hint="leave blank to generate from the title"><input value={form.slug} onChange={(e) => update('slug', e.target.value)} placeholder="get-promoted" className={input} /></Field>
            <Field label="Subtitle"><input value={form.subtitle} onChange={(e) => update('subtitle', e.target.value)} maxLength={300} className={input} /></Field>
            <Field label="Short description" hint="shown on cards"><textarea rows={2} value={form.shortDescription} onChange={(e) => update('shortDescription', e.target.value)} maxLength={600} className={input} /></Field>
          </Section>
          <Section title="Courses" description="In the order learners should take them.">
            <ProgramPicker programs={form.programs} onChange={(programs) => update('programs', programs)} />
          </Section>
          <Section title="Description" description="Optional longer introduction shown on the path page.">
            <ArticleBlockEditor blocks={form.description} onChange={(v) => update('description', v)} />
          </Section>
          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the title"><input value={form.seo.title} onChange={(e) => update('seo', { ...form.seo, title: e.target.value })} maxLength={300} className={input} /></Field>
            <Field label="Meta description" hint="falls back to the short description"><textarea rows={2} value={form.seo.description} onChange={(e) => update('seo', { ...form.seo, description: e.target.value })} maxLength={300} className={input} /></Field>
          </Section>
        </div>
        <div className="space-y-4">
          <Section title="Publishing">
            <label className="flex items-center gap-2 text-sm text-charcoal">
              <input type="checkbox" checked={form.featured} onChange={(e) => update('featured', e.target.checked)} /> Featured
            </label>
            <div className="flex flex-col gap-2">
              <button type="button" onClick={() => save('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60"><Save size={13} /> Save draft</button>
              <button type="button" onClick={() => save('published')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">Publish</button>
              {!isNew && form.status === 'published' && (
                <button type="button" onClick={() => save('archived')} disabled={saving} className="text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">Archive</button>
              )}
            </div>
          </Section>
          <Section title="Career goal" description="Used for deterministic “Recommended for your goals”.">
            <select value={form.careerGoal} onChange={(e) => update('careerGoal', e.target.value)} aria-label="Career goal" className={input}>
              <option value="">— None —</option>
              {CAREER_GOAL_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
            <select value={form.difficultyLevel} onChange={(e) => update('difficultyLevel', e.target.value)} aria-label="Level" className={input}>
              <option value="">Level — none</option>
              {Object.entries(LEVEL_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </Section>
          <Section title="Image">
            <MediaPicker label="Path image (optional)" aspect={16 / 9} value={form.heroMedia} onChange={(m) => update('heroMedia', m)} />
          </Section>
          {!isNew && (
            <button type="button" onClick={remove} className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-600"><Trash2 size={13} /> Delete learning path</button>
          )}
          <Link to="/admin/learning/paths" className="block text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">&larr; All learning paths</Link>
        </div>
      </div>
    </div>
  )
}
