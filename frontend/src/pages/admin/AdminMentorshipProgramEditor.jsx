import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, EyeOff } from 'lucide-react'
import {
  fetchProgram, createProgram, updateProgram, updateProgramStatus,
} from '../../api/mentorship'
import { fetchCountries } from '../../api/geography'
import { fetchTopics } from '../../api/taxonomies'
import { PROGRAM_STATUSES } from '../../constants/mentorship'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import MediaPicker from '../../components/cms/MediaPicker'
import ArticleBlockEditor from '../../components/cms/ArticleBlockEditor'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

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

function blankForm() {
  return {
    slug: '', name: '', shortDescription: '', fullDescription: [], publicVisible: false,
    applicationOpensAt: '', applicationClosesAt: '', programStartsAt: '', programEndsAt: '',
    mentorCapacity: '', menteeCapacity: '', countryCode: '', eligibilitySummary: '',
    heroMedia: null, topicSlugs: [], seo: {},
  }
}

function toForm(p) {
  return {
    slug: p.slug, name: p.name, shortDescription: p.shortDescription, fullDescription: p.fullDescription,
    publicVisible: p.publicVisible, applicationOpensAt: p.applicationOpensAt?.slice(0, 16) || '',
    applicationClosesAt: p.applicationClosesAt?.slice(0, 16) || '', programStartsAt: p.programStartsAt || '',
    programEndsAt: p.programEndsAt || '', mentorCapacity: p.mentorCapacity ?? '', menteeCapacity: p.menteeCapacity ?? '',
    countryCode: p.countryCode || '', eligibilitySummary: p.eligibilitySummary, heroMedia: p.heroMedia,
    topicSlugs: p.topicSlugs, seo: p.seo,
  }
}

export default function AdminMentorshipProgramEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [program, setProgram] = useState(isNew ? null : undefined)
  const [form, setForm] = useState(isNew ? blankForm() : null)
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  function load() {
    let active = true
    Promise.all([fetchCountries(), fetchTopics(), isNew ? Promise.resolve(null) : fetchProgram(id)])
      .then(([countryList, topicList, existing]) => {
        if (!active) return
        setCountries(countryList)
        setTopics(topicList)
        if (isNew) return
        if (!existing) {
          setNotFound(true)
          return
        }
        setProgram(existing)
        setForm(toForm(existing))
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError('Something went wrong loading this program. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      if (isNew) {
        const created = await createProgram(form)
        toast.success('Program created as Draft.')
        navigate(`/admin/mentorship/programs/${created.id}`)
      } else {
        const updated = await updateProgram(id, form)
        setProgram(updated)
        setForm(toForm(updated))
        toast.success('Program updated.')
      }
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this program.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateProgramStatus(id, status)
      setProgram(updated)
      toast.success(`Program marked ${status.replace(/_/g, ' ')}.`)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this program" description={loadError} />
  if (notFound) return <EmptyState title="Program not found" description="This program may have been removed or the URL is incorrect." />
  if (form === null || (!isNew && !program)) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New mentorship program' : program.name}
        description="Program details, dates, capacity, and publishing."
        actions={!isNew && program && <StatusBadge status={program.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-6">
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Basic information</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Name">
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Slug" hint="URL-safe identifier">
                <input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Short description">
                <textarea rows={2} value={form.shortDescription} onChange={(e) => setForm({ ...form, shortDescription: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <MediaPicker label="Hero media (optional)" value={form.heroMedia} onChange={(m) => setForm({ ...form, heroMedia: m })} aspect={16 / 9} />
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Full description</p>
            <ArticleBlockEditor blocks={form.fullDescription} onChange={(fullDescription) => setForm({ ...form, fullDescription })} />
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Application window</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Applications open" hint="optional">
                <input type="datetime-local" value={form.applicationOpensAt} onChange={(e) => setForm({ ...form, applicationOpensAt: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Applications close" hint="optional">
                <input type="datetime-local" value={form.applicationClosesAt} onChange={(e) => setForm({ ...form, applicationClosesAt: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Program dates &amp; capacity</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Program starts" hint="optional">
                <input type="date" value={form.programStartsAt} onChange={(e) => setForm({ ...form, programStartsAt: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Program ends" hint="optional">
                <input type="date" value={form.programEndsAt} onChange={(e) => setForm({ ...form, programEndsAt: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Mentor capacity" hint="optional, total slots">
                <input type="number" min="0" value={form.mentorCapacity} onChange={(e) => setForm({ ...form, mentorCapacity: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Mentee capacity" hint="optional, total slots">
                <input type="number" min="0" value={form.menteeCapacity} onChange={(e) => setForm({ ...form, menteeCapacity: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Geography &amp; focus</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Country / scope" hint="optional — leave blank for globally open">
                <select value={form.countryCode} onChange={(e) => setForm({ ...form, countryCode: e.target.value })} className={inputClass}>
                  <option value="">Global</option>
                  {countries.map((c) => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Focus topics" hint="optional">
              <div className="mt-1 flex flex-wrap gap-2">
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
            <div className="mt-4">
              <Field label="Eligibility summary" hint="optional">
                <textarea rows={2} value={form.eligibilitySummary} onChange={(e) => setForm({ ...form, eligibilitySummary: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              <Save size={13} /> {saving ? 'Saving…' : isNew ? 'Create program' : 'Save changes'}
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {!isNew && program && (
            <div className="border border-taupe-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
              <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
                <input
                  type="checkbox"
                  checked={form.publicVisible}
                  onChange={async (e) => {
                    const publicVisible = e.target.checked
                    setForm({ ...form, publicVisible })
                    try {
                      const updated = await updateProgram(id, { ...form, publicVisible })
                      setProgram(updated)
                      toast.success(publicVisible ? 'Program is now publicly visible.' : 'Program hidden from the public page.')
                    } catch (err) {
                      toast.error(err?.apiError?.message || 'Something went wrong.')
                    }
                  }}
                />
                Publicly visible
              </label>
              <p className="mt-1 text-xs text-charcoal-600/60">Independent of status — an Open program stays hidden until this is on.</p>

              <div className="mt-4 space-y-2">
                {PROGRAM_STATUSES.filter((s) => s !== program.status).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => (s === 'archived' ? setConfirmAction({ status: s }) : applyStatus(s))}
                    className="btn-secondary w-full !py-2 text-xs capitalize"
                  >
                    {s === 'applications_open' && <Eye size={13} />}
                    {s === 'applications_closed' && <EyeOff size={13} />}
                    {s.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
          )}
          {isNew && (
            <div className="border border-dashed border-taupe-300 bg-taupe-50 p-6 text-sm text-charcoal-600">
              Save this program first to manage its status and publishing.
            </div>
          )}

          <Link to="/admin/mentorship/programs" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all programs
          </Link>
        </div>
      </div>

      {confirmAction && (
        <ConfirmDialog
          title={`Mark as ${confirmAction.status.replace(/_/g, ' ')}?`}
          description="Archived programs are removed from active admin views but their record and history are preserved."
          confirmLabel="Archive"
          danger
          onConfirm={() => applyStatus(confirmAction.status)}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
