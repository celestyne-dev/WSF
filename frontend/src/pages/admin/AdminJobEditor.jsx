import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, AlertTriangle, Archive, Trash2, Copy } from 'lucide-react'
import { fetchJobBySlug, createJob, updateJob, deleteJob, duplicateJob } from '../../api/jobs'
import { fetchOrganizations } from '../../api/taxonomies'
import { fetchCountries, regionOptions } from '../../api/geography'
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

const STATUSES = ['draft', 'published', 'closed', 'archived']
const WORK_MODES = ['On-site', 'Hybrid', 'Remote']
const EMPLOYMENT_TYPES = ['Full-time', 'Part-time', 'Contract', 'Temporary', 'Internship']
const CAREER_LEVELS = ['Entry level', 'Junior', 'Mid-level', 'Senior', 'Manager', 'Director', 'Executive']
const SALARY_PERIODS = [
  { value: 'year', label: 'per year' },
  { value: 'month', label: 'per month' },
  { value: 'hour', label: 'per hour' },
]

function blankForm() {
  return {
    title: '',
    slug: '',
    organizationId: '',
    companyName: '',
    logoMedia: null,
    shortDescription: '',
    description: [],
    workMode: '',
    remoteScope: '',
    remoteRegion: '',
    employmentType: '',
    careerLevel: '',
    industry: '',
    countryCode: '',
    location: '',
    salaryMin: '',
    salaryMax: '',
    currency: '',
    salaryPeriod: 'year',
    applicationUrl: '',
    applicationInstructions: '',
    deadline: '',
    expiryDate: '',
    featured: false,
    sponsored: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(job) {
  return {
    title: job.title || '',
    slug: job.slug || '',
    organizationId: job.organizationId || '',
    companyName: job.company || '',
    logoMedia: job.logoMediaId ? { ...job.logoMedia, id: job.logoMediaId } : null,
    shortDescription: job.shortDescription || '',
    description: job.description || [],
    workMode: job.workMode || '',
    remoteScope: job.remoteScope || '',
    remoteRegion: job.remoteRegion || '',
    employmentType: job.employmentType || '',
    careerLevel: job.careerLevel || '',
    industry: job.industry || '',
    countryCode: job.countryCode || '',
    location: job.location || '',
    salaryMin: job.salaryMin ?? '',
    salaryMax: job.salaryMax ?? '',
    currency: job.currency || '',
    salaryPeriod: job.salaryPeriod || 'year',
    applicationUrl: job.applicationUrl || '',
    applicationInstructions: job.applicationInstructions || '',
    deadline: job.deadline || '',
    expiryDate: job.expiryDate || '',
    featured: !!job.featured,
    sponsored: !!job.sponsored,
    status: job.status || 'draft',
    seoTitle: job.seo?.title || '',
    seoDescription: job.seo?.description || '',
    seoCanonical: job.seo?.canonical || '',
    seoOgMedia: job.seo?.ogImageMediaId ? { id: job.seo.ogImageMediaId } : null,
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

export default function AdminJobEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [organizations, setOrganizations] = useState([])
  const [countries, setCountries] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchOrganizations({ pageSize: 200 }), fetchCountries(), isNew ? Promise.resolve(null) : fetchJobBySlug(id)])
      .then(([orgRes, countryList, existing]) => {
        if (!active) return
        setOrganizations(orgRes.items)
        setCountries([...countryList].sort((a, b) => a.name.localeCompare(b.name)))
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the job editor. Please try again.'))
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
      if (field === 'organizationId' && value) {
        const org = organizations.find((o) => String(o.id) === String(value))
        if (org && !prev.companyName) next.companyName = org.name
      }
      if (field === 'workMode' && value !== 'Remote') {
        next.remoteScope = ''
        next.remoteRegion = ''
      }
      if (field === 'remoteScope' && value !== 'region') {
        next.remoteRegion = ''
      }
      return next
    })
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a job slug.`
    return null
  }

  const selectedOrg = organizations.find((o) => String(o.id) === String(form?.organizationId))
  const hasNoEmployer = form && !form.organizationId && !form.companyName
  const hasNoDescription = form && form.description.length === 0
  const hasNoApplicationUrl = form && !form.applicationUrl
  const salaryRangeInvalid = form && form.salaryMin !== '' && form.salaryMax !== '' && Number(form.salaryMin) > Number(form.salaryMax)
  const dateOrderInvalid = form && form.deadline && form.expiryDate && form.deadline > form.expiryDate

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (hasNoEmployer) {
      toast.error('Select an organization or enter a company name.')
      return
    }
    if (salaryRangeInvalid) {
      toast.error('Minimum salary cannot exceed maximum salary.')
      return
    }
    if (dateOrderInvalid) {
      toast.error("Application deadline cannot be after the listing's expiry date.")
      return
    }
    if (nextStatus === 'published') {
      if (hasNoDescription) {
        toast.error('Add a job description before publishing.')
        return
      }
      if (hasNoApplicationUrl) {
        toast.error('Add an application URL before publishing — WSF never shows a fake Apply button.')
        return
      }
    }
    setErrors({})
    setSaving(true)

    const payload = {
      title: form.title,
      slug: form.slug,
      organizationId: form.organizationId || null,
      companyName: form.companyName || selectedOrg?.name || null,
      logoMediaId: form.logoMedia?.id || null,
      shortDescription: form.shortDescription || null,
      description: form.description,
      workMode: form.workMode || null,
      remoteScope: form.workMode === 'Remote' ? form.remoteScope || null : null,
      remoteRegion: form.remoteScope === 'region' ? form.remoteRegion || null : null,
      employmentType: form.employmentType || null,
      careerLevel: form.careerLevel || null,
      industry: form.industry || null,
      countryCode: form.countryCode || null,
      location: form.location || null,
      salaryMin: form.salaryMin === '' ? null : Number(form.salaryMin),
      salaryMax: form.salaryMax === '' ? null : Number(form.salaryMax),
      currency: form.currency || null,
      salaryPeriod: form.salaryPeriod || null,
      applicationUrl: form.applicationUrl || null,
      applicationInstructions: form.applicationInstructions || null,
      deadline: form.deadline || null,
      expiryDate: form.expiryDate || null,
      featured: form.featured,
      sponsored: form.sponsored,
      status: nextStatus,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
    }

    try {
      const saved = isNew ? await createJob(payload) : await updateJob(id, payload)
      toast.success(`Job ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/jobs/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this job. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.title}? This can't be undone.`)) return
    try {
      await deleteJob(id)
      toast.success('Job deleted.')
      navigate('/admin/jobs')
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong deleting this job.'
      toast.error(message)
    }
  }

  async function handleDuplicate() {
    try {
      const copy = await duplicateJob(id)
      toast.success('Job duplicated as a new draft.')
      navigate(`/admin/jobs/${copy.slug}`)
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong duplicating this job.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the job editor" description={loadError} />
  if (notFound) return <EmptyState title="Job not found" description="This job may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Job' : `Edit: ${form.title || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/jobs/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && (
              <button type="button" onClick={handleDuplicate} className="btn-secondary !px-4 !py-2 text-xs">
                <Copy size={14} /> Duplicate
              </button>
            )}
            {!isNew && form.slug && (
              <a href={`/jobs/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Job title">
              <input value={form.title} onChange={(e) => updateField('title', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/jobs/${form.slug || 'your-slug'}`}>
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
            <Field label="Short summary" hint="shown on job cards">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Industry" hint="optional">
              <input value={form.industry} onChange={(e) => updateField('industry', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Employer" description="Use an existing Organization wherever possible — its logo and details are reused automatically.">
            <Field label="Organization" hint="optional">
              <select value={form.organizationId} onChange={(e) => updateField('organizationId', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {organizations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} {o.status !== 'published' ? `(${o.status})` : ''}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Company name" hint={selectedOrg ? 'auto-filled from the selected organization — override if needed' : 'required when no organization is selected'}>
              <input value={form.companyName} onChange={(e) => updateField('companyName', e.target.value)} placeholder={selectedOrg?.name || ''} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            {!selectedOrg && (
              <MediaPicker label="Job-specific logo (only needed when no organization is linked)" aspect={1} value={form.logoMedia} onChange={(media) => updateField('logoMedia', media)} />
            )}
          </Section>

          <Section title="Job description" description="Structure the content however makes sense — About the role, Responsibilities, Requirements, Benefits, How to apply — you decide the headings.">
            <ArticleBlockEditor blocks={form.description} onChange={(description) => updateField('description', description)} />
          </Section>

          <Section title="Employment details">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Employment type">
                <select value={form.employmentType} onChange={(e) => updateField('employmentType', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {EMPLOYMENT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Career level">
                <select value={form.careerLevel} onChange={(e) => updateField('careerLevel', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {CAREER_LEVELS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </Section>

          <Section title="Location / remote">
            <Field label="Work mode">
              <select value={form.workMode} onChange={(e) => updateField('workMode', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {WORK_MODES.map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
            </Field>
            {form.workMode === 'Remote' && (
              <Field label="Remote scope">
                <select value={form.remoteScope} onChange={(e) => updateField('remoteScope', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  <option value="worldwide">Remote worldwide</option>
                  <option value="country">Remote within a country</option>
                  <option value="region">Remote within a region</option>
                </select>
              </Field>
            )}
            {form.workMode === 'Remote' && form.remoteScope === 'region' && (
              <Field label="Remote region">
                <select value={form.remoteRegion} onChange={(e) => updateField('remoteRegion', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {regionOptions().map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Country" hint={form.remoteScope === 'country' ? 'the single country this remote role is restricted to' : 'optional'}>
                <select value={form.countryCode} onChange={(e) => updateField('countryCode', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {countries.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="City / location" hint="optional">
                <input value={form.location} onChange={(e) => updateField('location', e.target.value)} placeholder="Nairobi, Kenya" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="Compensation" description="Leave blank if the employer doesn't want salary disclosed publicly.">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Minimum salary" hint="optional">
                <input type="number" value={form.salaryMin} onChange={(e) => updateField('salaryMin', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Maximum salary" hint="optional">
                <input type="number" value={form.salaryMax} onChange={(e) => updateField('salaryMax', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Period">
                <select value={form.salaryPeriod} onChange={(e) => updateField('salaryPeriod', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  {SALARY_PERIODS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Currency" hint="ISO code, e.g. USD, KES, EUR">
              <input value={form.currency} onChange={(e) => updateField('currency', e.target.value.toUpperCase().slice(0, 3))} className="w-32 border border-taupe-300 px-3 py-2.5 text-sm uppercase focus:border-burgundy-500 focus:outline-none" />
            </Field>
            {salaryRangeInvalid && (
              <p className="text-xs text-rose-600">Minimum salary cannot exceed maximum salary.</p>
            )}
          </Section>

          <Section title="Application">
            <Field label="Application URL" hint="where WSF sends candidates to apply">
              <input value={form.applicationUrl} onChange={(e) => updateField('applicationUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Application instructions" hint="optional — shown alongside the Apply button">
              <textarea rows={2} value={form.applicationInstructions} onChange={(e) => updateField('applicationInstructions', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the job title">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the short summary">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint="only set this if this listing is republished from elsewhere">
              <input value={form.seoCanonical} onChange={(e) => updateField('seoCanonical', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <MediaPicker label="Social / OG image" aspect={1.91 / 1} value={form.seoOgMedia} onChange={(media) => updateField('seoOgMedia', media)} />
          </Section>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing / deadline</p>
            <select value={form.status} onChange={(e) => updateField('status', e.target.value)} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <Field label="Application deadline" hint="optional">
              <input type="date" value={form.deadline} onChange={(e) => updateField('deadline', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
            </Field>
            <Field label="Listing expiry" hint="optional — when this listing stops appearing as active">
              <input type="date" value={form.expiryDate} onChange={(e) => updateField('expiryDate', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
            </Field>
            {dateOrderInvalid && <p className="text-xs text-rose-600">Deadline can't be after the expiry date.</p>}

            {hasNoEmployer && (
              <div className="mt-3 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Select an organization or enter a company name.</span>
              </div>
            )}
            {hasNoDescription && (
              <div className="mt-3 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add a job description before publishing.</span>
              </div>
            )}
            {hasNoApplicationUrl && (
              <div className="mt-3 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add an application URL before publishing.</span>
              </div>
            )}

            <div className="mt-4 space-y-2">
              <button type="button" onClick={() => handleSave('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                <Save size={13} /> {saving ? 'Saving…' : 'Save draft'}
              </button>
              <button type="button" onClick={() => handleSave('published')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                Publish
              </button>
              {!isNew && form.status !== 'closed' && (
                <button type="button" onClick={() => handleSave('closed')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  Close to applications
                </button>
              )}
              {!isNew && form.status !== 'archived' && (
                <button type="button" onClick={() => handleSave('archived')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  <Archive size={13} /> Archive
                </button>
              )}
              {!isNew && (
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  <Trash2 size={13} className="mr-1 inline" /> Delete job
                </button>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Promotion / sponsorship</p>
            <p className="mt-1 text-xs text-charcoal-600/70">CMS readiness only — no payment or checkout in this release.</p>
            <div className="mt-3 space-y-2">
              <label className="flex items-center gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
                Featured
              </label>
              <label className="flex items-center gap-2 text-sm text-charcoal-600">
                <input type="checkbox" checked={form.sponsored} onChange={(e) => updateField('sponsored', e.target.checked)} />
                Sponsored
              </label>
            </div>
          </div>

          <Link to="/admin/jobs" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all jobs
          </Link>
        </div>
      </div>
    </div>
  )
}
