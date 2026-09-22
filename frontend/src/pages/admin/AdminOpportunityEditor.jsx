import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, AlertTriangle, Archive, Trash2 } from 'lucide-react'
import { fetchOpportunityBySlug, createOpportunity, updateOpportunity, deleteOpportunity } from '../../api/opportunities'
import { fetchOrganizations, fetchTopics } from '../../api/taxonomies'
import { fetchCountries } from '../../api/geography'
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
const TYPES = [
  'Scholarship',
  'Fellowship',
  'Grant',
  'Award',
  'Competition',
  'Accelerator',
  'Incubator',
  'Training Program',
  'Mentorship Program',
  'Internship',
  'Volunteer Opportunity',
  'Conference Opportunity',
  'Funding Opportunity',
  'Other',
]
const FUNDING_TYPES = [
  { value: 'fully_funded', label: 'Fully funded' },
  { value: 'partially_funded', label: 'Partially funded' },
  { value: 'stipend', label: 'Stipend only' },
  { value: 'unpaid', label: 'Unpaid' },
  { value: 'not_applicable', label: 'Not applicable' },
]

function blankForm() {
  return {
    title: '',
    slug: '',
    organizationId: '',
    organizationName: '',
    logoMedia: null,
    type: '',
    shortDescription: '',
    description: [],
    eligibility: '',
    eligibilityNotes: '',
    careerStage: '',
    countriesEligible: [],
    location: '',
    fundingType: '',
    fundingMin: '',
    fundingMax: '',
    currency: '',
    fundingValue: '',
    applicationUrl: '',
    applicationInstructions: '',
    openingDate: '',
    deadline: '',
    expiryDate: '',
    topicSlugs: [],
    featured: false,
    sponsored: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(opportunity) {
  return {
    title: opportunity.title || '',
    slug: opportunity.slug || '',
    organizationId: opportunity.organizationId || '',
    organizationName: opportunity.organization || '',
    logoMedia: opportunity.logoMedia || null,
    type: opportunity.type || '',
    shortDescription: opportunity.shortDescription || '',
    description: opportunity.description || [],
    eligibility: opportunity.eligibility || '',
    eligibilityNotes: opportunity.eligibilityNotes || '',
    careerStage: opportunity.careerStage || '',
    countriesEligible: opportunity.countriesEligible || [],
    location: opportunity.location || '',
    fundingType: opportunity.fundingType || '',
    fundingMin: opportunity.fundingMin ?? '',
    fundingMax: opportunity.fundingMax ?? '',
    currency: opportunity.currency || '',
    fundingValue: opportunity.fundingValue || '',
    applicationUrl: opportunity.applicationUrl || '',
    applicationInstructions: opportunity.applicationInstructions || '',
    openingDate: opportunity.openingDate || '',
    deadline: opportunity.deadline || '',
    expiryDate: opportunity.expiryDate || '',
    topicSlugs: opportunity.topicSlugs || [],
    featured: !!opportunity.featured,
    sponsored: !!opportunity.sponsored,
    status: opportunity.status || 'draft',
    seoTitle: opportunity.seo?.title || '',
    seoDescription: opportunity.seo?.description || '',
    seoCanonical: opportunity.seo?.canonical || '',
    seoOgMedia: opportunity.seo?.ogImageMediaId ? { id: opportunity.seo.ogImageMediaId } : null,
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

export default function AdminOpportunityEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [organizations, setOrganizations] = useState([])
  const [countries, setCountries] = useState([])
  const [topics, setTopics] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([
      fetchOrganizations({ pageSize: 200 }),
      fetchCountries(),
      fetchTopics(),
      isNew ? Promise.resolve(null) : fetchOpportunityBySlug(id),
    ])
      .then(([orgRes, countryList, topicList, existing]) => {
        if (!active) return
        setOrganizations(orgRes.items)
        setCountries([...countryList].sort((a, b) => a.name.localeCompare(b.name)))
        setTopics(topicList)
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the opportunity editor. Please try again.'))
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
        if (org && !prev.organizationName) next.organizationName = org.name
      }
      return next
    })
  }

  function toggleCountry(code) {
    setForm((prev) => ({
      ...prev,
      countriesEligible: prev.countriesEligible.includes(code)
        ? prev.countriesEligible.filter((c) => c !== code)
        : [...prev.countriesEligible, code],
    }))
  }

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as an opportunity slug.`
    return null
  }

  const selectedOrg = organizations.find((o) => String(o.id) === String(form?.organizationId))
  const hasNoProvider = form && !form.organizationId && !form.organizationName
  const hasNoDescription = form && form.description.length === 0
  const hasNoApplicationUrl = form && !form.applicationUrl
  const fundingRangeInvalid = form && form.fundingMin !== '' && form.fundingMax !== '' && Number(form.fundingMin) > Number(form.fundingMax)
  const openingAfterDeadline = form && form.openingDate && form.deadline && form.openingDate > form.deadline
  const deadlineAfterExpiry = form && form.deadline && form.expiryDate && form.deadline > form.expiryDate

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (hasNoProvider) {
      toast.error('Select an organization or enter a provider name.')
      return
    }
    if (fundingRangeInvalid) {
      toast.error('Minimum funding cannot exceed maximum funding.')
      return
    }
    if (openingAfterDeadline) {
      toast.error('Opening date must be before the application deadline.')
      return
    }
    if (deadlineAfterExpiry) {
      toast.error("Application deadline cannot be after the listing's expiry date.")
      return
    }
    if (nextStatus === 'published') {
      if (hasNoDescription) {
        toast.error('Add a description before publishing.')
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
      organizationName: form.organizationName || selectedOrg?.name || null,
      logoMediaId: form.logoMedia?.id || null,
      type: form.type || null,
      shortDescription: form.shortDescription || null,
      description: form.description,
      eligibility: form.eligibility || null,
      eligibilityNotes: form.eligibilityNotes || null,
      careerStage: form.careerStage || null,
      countriesEligible: form.countriesEligible,
      location: form.location || null,
      fundingType: form.fundingType || null,
      fundingMin: form.fundingMin === '' ? null : Number(form.fundingMin),
      fundingMax: form.fundingMax === '' ? null : Number(form.fundingMax),
      currency: form.currency || null,
      fundingValue: form.fundingValue || null,
      applicationUrl: form.applicationUrl || null,
      applicationInstructions: form.applicationInstructions || null,
      openingDate: form.openingDate || null,
      deadline: form.deadline || null,
      expiryDate: form.expiryDate || null,
      topicSlugs: form.topicSlugs,
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
      const saved = isNew ? await createOpportunity(payload) : await updateOpportunity(id, payload)
      toast.success(`Opportunity ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/opportunities/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this opportunity. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.title}? This can't be undone.`)) return
    try {
      await deleteOpportunity(id)
      toast.success('Opportunity deleted.')
      navigate('/admin/opportunities')
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong deleting this opportunity.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the opportunity editor" description={loadError} />
  if (notFound) return <EmptyState title="Opportunity not found" description="This opportunity may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Opportunity' : `Edit: ${form.title || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/opportunities/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && (
              <a href={`/opportunities/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
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
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/opportunities/${form.slug || 'your-slug'}`}>
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
            <Field label="Short summary" hint="shown on opportunity cards">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Opportunity type">
              <select value={form.type} onChange={(e) => updateField('type', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
          </Section>

          <Section title="Provider" description="Use an existing Organization wherever possible — its logo and details are reused automatically.">
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
            <Field label="Provider name" hint={selectedOrg ? 'auto-filled from the selected organization — override if needed' : 'required when no organization is selected'}>
              <input value={form.organizationName} onChange={(e) => updateField('organizationName', e.target.value)} placeholder={selectedOrg?.name || ''} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            {!selectedOrg && (
              <MediaPicker label="Opportunity-specific logo (only needed when no organization is linked)" aspect={1} value={form.logoMedia} onChange={(media) => updateField('logoMedia', media)} />
            )}
          </Section>

          <Section title="Description" description="Structure the content however makes sense — About, What's offered, Eligibility, How to apply — you decide the headings.">
            <ArticleBlockEditor blocks={form.description} onChange={(description) => updateField('description', description)} />
          </Section>

          <Section
            title="Geography &amp; eligibility"
            description="Select every country this opportunity is open to, or choose Global for worldwide eligibility. Eligibility should describe what's actually true for this opportunity — nothing is assumed."
          >
            <Field label="Eligible countries" hint="select Global for worldwide eligibility, or Remote for remote-only opportunities">
              <div className="flex max-h-56 flex-wrap gap-1.5 overflow-y-auto border border-taupe-200 p-3">
                {countries.map((c) => (
                  <button
                    key={c.code}
                    type="button"
                    onClick={() => toggleCountry(c.code)}
                    className={`px-2.5 py-1 text-xs font-medium ${form.countriesEligible.includes(c.code) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Eligibility summary" hint="short, scannable — shown prominently on the public page">
              <textarea rows={2} value={form.eligibility} onChange={(e) => updateField('eligibility', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Career stage" hint="optional — free text, e.g. Early-career, Founders">
              <input value={form.careerStage} onChange={(e) => updateField('careerStage', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Additional eligibility notes" hint="optional — age, gender, education, or experience requirements, only if genuinely applicable to this opportunity">
              <textarea rows={2} value={form.eligibilityNotes} onChange={(e) => updateField('eligibilityNotes', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Location" hint="optional free text, e.g. Hybrid — sessions in London and New York">
              <input value={form.location} onChange={(e) => updateField('location', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Funding / value" description="Leave blank where a field genuinely doesn't apply — don't fabricate figures.">
            <Field label="Funding type">
              <select value={form.fundingType} onChange={(e) => updateField('fundingType', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {FUNDING_TYPES.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Minimum amount" hint="optional">
                <input type="number" value={form.fundingMin} onChange={(e) => updateField('fundingMin', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Maximum amount" hint="optional">
                <input type="number" value={form.fundingMax} onChange={(e) => updateField('fundingMax', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Currency" hint="ISO code, e.g. USD, KES, EUR">
                <input value={form.currency} onChange={(e) => updateField('currency', e.target.value.toUpperCase().slice(0, 3))} className="w-full border border-taupe-300 px-3 py-2.5 text-sm uppercase focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
            {fundingRangeInvalid && <p className="text-xs text-rose-600">Minimum funding cannot exceed maximum funding.</p>}
            <Field label="Funding summary" hint="free text shown on cards, e.g. $10,000 grant + mentorship">
              <input value={form.fundingValue} onChange={(e) => updateField('fundingValue', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Application">
            <Field label="Application URL" hint="where WSF sends candidates to apply">
              <input value={form.applicationUrl} onChange={(e) => updateField('applicationUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Application instructions" hint="optional — shown alongside the Apply button">
              <textarea rows={2} value={form.applicationInstructions} onChange={(e) => updateField('applicationInstructions', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Topics" description="Optional — helps this opportunity surface in related content.">
            <div className="flex flex-wrap gap-1.5">
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
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the opportunity title">
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
            <Field label="Opening date" hint="optional — when applications open">
              <input type="date" value={form.openingDate} onChange={(e) => updateField('openingDate', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
            </Field>
            <Field label="Application deadline" hint="optional">
              <input type="date" value={form.deadline} onChange={(e) => updateField('deadline', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
            </Field>
            <Field label="Listing expiry" hint="optional — when this listing stops appearing as active">
              <input type="date" value={form.expiryDate} onChange={(e) => updateField('expiryDate', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
            </Field>
            {openingAfterDeadline && <p className="text-xs text-rose-600">Opening date must be before the deadline.</p>}
            {deadlineAfterExpiry && <p className="text-xs text-rose-600">Deadline can't be after the expiry date.</p>}

            {hasNoProvider && (
              <div className="mt-3 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Select an organization or enter a provider name.</span>
              </div>
            )}
            {hasNoDescription && (
              <div className="mt-3 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add a description before publishing.</span>
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
                  <Trash2 size={13} className="mr-1 inline" /> Delete opportunity
                </button>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Promotion / sponsorship</p>
            <p className="mt-1 text-xs text-charcoal-600/70">CMS readiness only — no payment or invoicing in this release.</p>
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

          <Link to="/admin/opportunities" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all opportunities
          </Link>
        </div>
      </div>
    </div>
  )
}
