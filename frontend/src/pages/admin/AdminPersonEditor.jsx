import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, AlertTriangle, X, Archive, Trash2 } from 'lucide-react'
import { fetchPersonBySlug, createPerson, updatePerson, deletePerson } from '../../api/people'
import { fetchOrganizations, fetchSeries } from '../../api/taxonomies'
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

function blankForm() {
  return {
    name: '',
    slug: '',
    pronouns: '',
    title: '',
    shortBio: '',
    bio: [],
    organizationId: '',
    industry: '',
    profession: '',
    location: '',
    countryCode: '',
    photoMedia: null,
    expertise: [],
    achievements: [],
    careerTimeline: [],
    awards: [],
    featuredQuote: '',
    website: '',
    socialLinkedin: '',
    socialTwitter: '',
    socialInstagram: '',
    seriesSlugs: [],
    featured: false,
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(person) {
  return {
    name: person.name || '',
    slug: person.slug || '',
    pronouns: person.pronouns || '',
    title: person.title || '',
    shortBio: person.shortBio || '',
    bio: person.bio || [],
    organizationId: person.organizationId || '',
    industry: person.industry || '',
    profession: person.profession || '',
    location: person.location || '',
    countryCode: person.countryCode || '',
    photoMedia: person.photoMediaId ? { ...person.photoMedia, id: person.photoMediaId } : null,
    expertise: person.expertise || [],
    achievements: person.achievements || [],
    careerTimeline: person.careerTimeline || [],
    awards: person.awards || [],
    featuredQuote: person.featuredQuote || '',
    website: person.website || '',
    socialLinkedin: person.social?.linkedin || '',
    socialTwitter: person.social?.twitter || '',
    socialInstagram: person.social?.instagram || '',
    seriesSlugs: person.seriesSlugs || [],
    featured: !!person.featured,
    status: person.status || 'draft',
    seoTitle: person.seo?.title || '',
    seoDescription: person.seo?.description || '',
    seoCanonical: person.seo?.canonical || '',
    seoOgMedia: person.seo?.ogImageMediaId ? { id: person.seo.ogImageMediaId } : null,
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

function ListEditor({ value, onChange, placeholder = 'Add an item and press Enter' }) {
  const [draft, setDraft] = useState('')

  function commit() {
    const text = draft.trim()
    if (text && !value.includes(text)) onChange([...value, text])
    setDraft('')
  }

  return (
    <div>
      <div className="space-y-1.5">
        {value.map((item) => (
          <div key={item} className="flex items-center justify-between gap-2 bg-taupe-100 px-2.5 py-1.5 text-xs text-charcoal-600">
            <span>{item}</span>
            <button type="button" onClick={() => onChange(value.filter((v) => v !== item))} aria-label={`Remove ${item}`} className="hover:text-rose-600">
              <X size={11} />
            </button>
          </div>
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
          placeholder={placeholder}
          className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
        />
        <button type="button" onClick={commit} className="btn-secondary shrink-0 !px-3 !py-2 text-xs">
          Add
        </button>
      </div>
    </div>
  )
}

function TimelineEditor({ value, onChange }) {
  function update(i, field, val) {
    onChange(value.map((item, idx) => (idx === i ? { ...item, [field]: val } : item)))
  }
  return (
    <div className="space-y-2">
      {value.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            value={item.year || ''}
            onChange={(e) => update(i, 'year', e.target.value)}
            placeholder="Year"
            className="w-24 border border-taupe-300 px-2 py-1.5 text-xs focus:border-burgundy-500 focus:outline-none"
          />
          <input
            value={item.title || ''}
            onChange={(e) => update(i, 'title', e.target.value)}
            placeholder="Role or milestone"
            className="flex-1 border border-taupe-300 px-2 py-1.5 text-xs focus:border-burgundy-500 focus:outline-none"
          />
          <button type="button" onClick={() => onChange(value.filter((_, idx) => idx !== i))} aria-label="Remove" className="text-charcoal-600 hover:text-rose-600">
            <X size={13} />
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...value, { year: '', title: '' }])} className="btn-secondary !px-3 !py-1.5 text-xs">
        + Add milestone
      </button>
    </div>
  )
}

export default function AdminPersonEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [organizations, setOrganizations] = useState([])
  const [series, setSeries] = useState([])
  const [countries, setCountries] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([fetchOrganizations({ pageSize: 200 }), fetchSeries(), fetchCountries(), isNew ? Promise.resolve(null) : fetchPersonBySlug(id)])
      .then(([orgRes, seriesList, countryList, existing]) => {
        if (!active) return
        setOrganizations(orgRes.items)
        setSeries(seriesList)
        setCountries([...countryList].sort((a, b) => a.name.localeCompare(b.name)))
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the person editor. Please try again.'))
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

  function toggleSeries(slug) {
    setForm((prev) => ({
      ...prev,
      seriesSlugs: prev.seriesSlugs.includes(slug) ? prev.seriesSlugs.filter((s) => s !== slug) : [...prev.seriesSlugs, slug],
    }))
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a person slug.`
    return null
  }

  const hasNoBio = form && !form.shortBio && form.bio.length === 0

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (nextStatus === 'published' && hasNoBio) {
      toast.error('Add a short introduction or biography before publishing this profile.')
      return
    }
    setErrors({})
    setSaving(true)

    const payload = {
      name: form.name,
      slug: form.slug,
      pronouns: form.pronouns || null,
      title: form.title || null,
      shortBio: form.shortBio || null,
      bio: form.bio,
      organizationId: form.organizationId || null,
      industry: form.industry || null,
      profession: form.profession || null,
      location: form.location || null,
      countryCode: form.countryCode || null,
      photoMediaId: form.photoMedia?.id || null,
      expertise: form.expertise,
      achievements: form.achievements,
      careerTimeline: form.careerTimeline,
      awards: form.awards,
      featuredQuote: form.featuredQuote || null,
      website: form.website || null,
      social: {
        linkedin: form.socialLinkedin || null,
        twitter: form.socialTwitter || null,
        instagram: form.socialInstagram || null,
      },
      seriesSlugs: form.seriesSlugs,
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
      const saved = isNew ? await createPerson(payload) : await updatePerson(id, payload)
      toast.success(`Profile ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/people/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this profile. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deletePerson(id)
      toast.success('Profile deleted.')
      navigate('/admin/people')
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'This person is referenced elsewhere and can\'t be deleted. Try archiving instead.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the person editor" description={loadError} />
  if (notFound) return <EmptyState title="Person not found" description="This profile may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Person' : `Edit: ${form.name || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/people/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && (
              <a href={`/people/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
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
              <Field label="Full name">
                <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Pronouns" hint="optional">
                <input value={form.pronouns} onChange={(e) => updateField('pronouns', e.target.value)} placeholder="she/her" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/people/${form.slug || 'your-slug'}`}>
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
            <Field label="Professional title / headline">
              <input value={form.title} onChange={(e) => updateField('title', e.target.value)} placeholder="Founder & CEO" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Short introduction" hint="a one or two sentence summary shown on cards and as the meta description fallback">
              <textarea rows={2} value={form.shortBio} onChange={(e) => updateField('shortBio', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Featured quote" hint="optional">
              <textarea rows={2} value={form.featuredQuote} onChange={(e) => updateField('featuredQuote', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Biography" description="The full profile story — this is what publishes on the public profile page.">
            <ArticleBlockEditor blocks={form.bio} onChange={(bio) => updateField('bio', bio)} />
          </Section>

          <Section title="Media">
            <MediaPicker label="Portrait" aspect={0.8} value={form.photoMedia} onChange={(media) => updateField('photoMedia', media)} />
          </Section>

          <Section title="Professional information">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Organization" hint="optional">
                <select value={form.organizationId} onChange={(e) => updateField('organizationId', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {organizations.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Industry / field" hint="optional">
                <input value={form.industry} onChange={(e) => updateField('industry', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
            <Field label="Profession / designation" hint="e.g. Founder & CEO — optional">
              <input value={form.profession} onChange={(e) => updateField('profession', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Areas of expertise">
              <ListEditor value={form.expertise} onChange={(v) => updateField('expertise', v)} />
            </Field>
            <Field label="Achievements">
              <ListEditor value={form.achievements} onChange={(v) => updateField('achievements', v)} />
            </Field>
            <Field label="Awards">
              <ListEditor value={form.awards} onChange={(v) => updateField('awards', v)} />
            </Field>
            <Field label="Career timeline">
              <TimelineEditor value={form.careerTimeline} onChange={(v) => updateField('careerTimeline', v)} />
            </Field>
          </Section>

          <Section title="Geography" description="Women Shaping Futures profiles women from every region — search any country.">
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
              <Field label="City / location" hint="optional">
                <input value={form.location} onChange={(e) => updateField('location', e.target.value)} placeholder="Nairobi, Kenya" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="Editorial relationships" description="Named editorial groupings live in Series — e.g. Women Doing Incredible Things, Founder Stories.">
            <div className="flex flex-wrap gap-2">
              {series.map((s) => (
                <button
                  key={s.slug}
                  type="button"
                  onClick={() => toggleSeries(s.slug)}
                  className={`px-2.5 py-1 text-xs font-medium ${form.seriesSlugs.includes(s.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                >
                  {s.name}
                </button>
              ))}
              {series.length === 0 && <p className="text-xs text-charcoal-600/70">No series exist yet — add one from the Series admin section.</p>}
            </div>
          </Section>

          <Section title="Social / links">
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
            <Field label="SEO title" hint="falls back to the person's name">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the short introduction">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Canonical URL" hint="only set this if the profile is republished from elsewhere">
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
                  {s}
                </option>
              ))}
            </select>
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
              Featured
            </label>

            {hasNoBio && (
              <div className="mt-4 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add a short introduction or biography before publishing.</span>
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
                  <Trash2 size={13} className="mr-1 inline" /> Delete profile
                </button>
              )}
            </div>
          </div>

          <Link to="/admin/people" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all people
          </Link>
        </div>
      </div>
    </div>
  )
}
