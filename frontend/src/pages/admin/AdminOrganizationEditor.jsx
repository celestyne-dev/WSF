import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, AlertTriangle, Archive, Trash2 } from 'lucide-react'
import { fetchOrganizationBySlug, createOrganization, updateOrganization, deleteOrganization } from '../../api/taxonomies'
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

const STATUSES = ['draft', 'published', 'archived']
const ORG_TYPES = [
  { value: '', label: '— None —' },
  { value: 'company', label: 'Company' },
  { value: 'nonprofit', label: 'Nonprofit' },
  { value: 'foundation', label: 'Foundation' },
  { value: 'government', label: 'Government organization' },
  { value: 'educational_institution', label: 'Educational institution' },
  { value: 'media_organization', label: 'Media organization' },
  { value: 'professional_association', label: 'Professional association' },
  { value: 'social_enterprise', label: 'Social enterprise' },
  { value: 'community_organization', label: 'Community organization' },
  { value: 'other', label: 'Other' },
]

function blankForm() {
  return {
    name: '',
    slug: '',
    type: '',
    industry: '',
    shortDescription: '',
    description: [],
    logoMedia: null,
    countryCode: '',
    location: '',
    foundedYear: '',
    website: '',
    socialLinkedin: '',
    socialTwitter: '',
    socialInstagram: '',
    featured: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(org) {
  return {
    name: org.name || '',
    slug: org.slug || '',
    type: org.type || '',
    industry: org.industry || '',
    shortDescription: org.shortDescription || '',
    description: org.description || [],
    logoMedia: org.logoMediaId ? { ...org.logoMedia, id: org.logoMediaId } : null,
    countryCode: org.countryCode || '',
    location: org.location || '',
    foundedYear: org.foundedYear || '',
    website: org.website || '',
    socialLinkedin: org.social?.linkedin || '',
    socialTwitter: org.social?.twitter || '',
    socialInstagram: org.social?.instagram || '',
    featured: !!org.featured,
    status: org.status || 'draft',
    seoTitle: org.seo?.title || '',
    seoDescription: org.seo?.description || '',
    seoCanonical: org.seo?.canonical || '',
    seoOgMedia: org.seo?.ogImageMediaId ? { id: org.seo.ogImageMediaId } : null,
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

export default function AdminOrganizationEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [countries, setCountries] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchCountries(), isNew ? Promise.resolve(null) : fetchOrganizationBySlug(id)])
      .then(([countryList, existing]) => {
        if (!active) return
        setCountries([...countryList].sort((a, b) => a.name.localeCompare(b.name)))
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the organization editor. Please try again.'))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as an organization slug.`
    return null
  }

  const hasNoDescription = form && !form.shortDescription && form.description.length === 0

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (nextStatus === 'published' && hasNoDescription) {
      toast.error('Add a short description or full description before publishing this organization.')
      return
    }
    setErrors({})
    setSaving(true)

    const payload = {
      name: form.name,
      slug: form.slug,
      type: form.type || null,
      industry: form.industry || null,
      shortDescription: form.shortDescription || null,
      description: form.description,
      logoMediaId: form.logoMedia?.id || null,
      countryCode: form.countryCode || null,
      location: form.location || null,
      foundedYear: form.foundedYear ? Number(form.foundedYear) : null,
      website: form.website || null,
      social: {
        linkedin: form.socialLinkedin || null,
        twitter: form.socialTwitter || null,
        instagram: form.socialInstagram || null,
      },
      featured: form.featured,
      status: nextStatus,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
    }

    try {
      const saved = isNew ? await createOrganization(payload) : await updateOrganization(id, payload)
      toast.success(`Organization ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/organizations/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this organization. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deleteOrganization(id)
      toast.success('Organization deleted.')
      navigate('/admin/organizations')
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'This organization is referenced elsewhere and can\'t be deleted. Try archiving instead.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the organization editor" description={loadError} />
  if (notFound) return <EmptyState title="Organization not found" description="This organization may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Organization' : `Edit: ${form.name || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/organizations/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && (
              <a href={`/organizations/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Organization name">
                <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Organization type">
                <select value={form.type} onChange={(e) => updateField('type', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  {ORG_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/organizations/${form.slug || 'your-slug'}`}>
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
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Industry" hint="optional">
                <input value={form.industry} onChange={(e) => updateField('industry', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Founded year" hint="optional">
                <input
                  type="number"
                  value={form.foundedYear}
                  onChange={(e) => updateField('foundedYear', e.target.value)}
                  placeholder="2019"
                  className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
              </Field>
            </div>
            <Field label="Short description" hint="shown on cards and as the meta description fallback">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="About / description" description="The full organization profile shown on the public detail page.">
            <ArticleBlockEditor blocks={form.description} onChange={(description) => updateField('description', description)} />
          </Section>

          <Section title="Media / logo" description="Rendered inside a controlled container — never cropped or stretched.">
            <MediaPicker label="Logo" aspect={1} value={form.logoMedia} onChange={(media) => updateField('logoMedia', media)} />
          </Section>

          <Section title="Geography">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Country">
                <select value={form.countryCode} onChange={(e) => updateField('countryCode', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {countries.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Headquarters city" hint="optional">
                <input value={form.location} onChange={(e) => updateField('location', e.target.value)} placeholder="Nairobi, Kenya" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="Website / links">
            <Field label="Website" hint="optional">
              <input value={form.website} onChange={(e) => updateField('website', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="LinkedIn" hint="username">
                <input value={form.socialLinkedin} onChange={(e) => updateField('socialLinkedin', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Twitter / X" hint="username">
                <input value={form.socialTwitter} onChange={(e) => updateField('socialTwitter', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Instagram" hint="username">
                <input value={form.socialInstagram} onChange={(e) => updateField('socialInstagram', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the organization's name">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the short description">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint="only set this if this profile is republished from elsewhere">
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
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
              Featured
            </label>

            {hasNoDescription && (
              <div className="mt-4 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add a short or full description before publishing.</span>
              </div>
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
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  <Trash2 size={13} className="mr-1 inline" /> Delete organization
                </button>
              )}
            </div>
          </div>

          <Link to="/admin/organizations" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all organizations
          </Link>
        </div>
      </div>
    </div>
  )
}
