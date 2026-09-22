import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, AlertTriangle, X, Archive, Trash2 } from 'lucide-react'
import { fetchAuthorBySlug, createAuthor, updateAuthor, deleteAuthor, fetchTopics } from '../../api/taxonomies'
import { fetchPeople } from '../../api/people'
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

const STATUSES = ['draft', 'active', 'archived']
const SUGGESTED_ROLES = ['Staff Writer', 'Contributor', 'Editor', 'Guest Contributor', 'Founder', 'Editorial Team']

function blankForm() {
  return {
    name: '',
    slug: '',
    role: '',
    shortBio: '',
    bio: [],
    photoMedia: null,
    location: '',
    countryCode: '',
    topicSlugs: [],
    personId: '',
    website: '',
    socialLinkedin: '',
    socialTwitter: '',
    socialInstagram: '',
    status: 'draft',
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(author) {
  return {
    name: author.name || '',
    slug: author.slug || '',
    role: author.role || '',
    shortBio: author.shortBio || '',
    bio: author.bio || [],
    photoMedia: author.photoMediaId ? { ...author.photoMedia, id: author.photoMediaId } : null,
    location: author.location || '',
    countryCode: author.countryCode || '',
    topicSlugs: author.topicSlugs || [],
    personId: author.personId || '',
    website: author.website || '',
    socialLinkedin: author.social?.linkedin || '',
    socialTwitter: author.social?.twitter || '',
    socialInstagram: author.social?.instagram || '',
    status: author.status || 'draft',
    seoTitle: author.seo?.title || '',
    seoDescription: author.seo?.description || '',
    seoCanonical: author.seo?.canonical || '',
    seoOgMedia: author.seo?.ogImageMediaId ? { id: author.seo.ogImageMediaId } : null,
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

export default function AdminAuthorEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [topics, setTopics] = useState([])
  const [people, setPeople] = useState([])
  const [countries, setCountries] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let active = true
    Promise.all([
      fetchTopics(),
      fetchPeople({ pageSize: 200 }),
      fetchCountries(),
      isNew ? Promise.resolve(null) : fetchAuthorBySlug(id),
    ])
      .then(([topicList, peopleRes, countryList, existing]) => {
        if (!active) return
        setTopics(topicList)
        setPeople(peopleRes.items)
        setCountries([...countryList].sort((a, b) => a.name.localeCompare(b.name)))
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the author editor. Please try again.'))
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

  function toggleTopic(slug) {
    setForm((prev) => ({
      ...prev,
      topicSlugs: prev.topicSlugs.includes(slug) ? prev.topicSlugs.filter((s) => s !== slug) : [...prev.topicSlugs, slug],
    }))
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as an author slug.`
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
    if (nextStatus === 'active' && hasNoBio) {
      toast.error('Add a short bio or biography before activating this author.')
      return
    }
    setErrors({})
    setSaving(true)

    const payload = {
      name: form.name,
      slug: form.slug,
      role: form.role || null,
      shortBio: form.shortBio || null,
      bio: form.bio,
      photoMediaId: form.photoMedia?.id || null,
      location: form.location || null,
      countryCode: form.countryCode || null,
      topicSlugs: form.topicSlugs,
      personId: form.personId || null,
      website: form.website || null,
      social: {
        linkedin: form.socialLinkedin || null,
        twitter: form.socialTwitter || null,
        instagram: form.socialInstagram || null,
      },
      status: nextStatus,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
    }

    try {
      const saved = isNew ? await createAuthor(payload) : await updateAuthor(id, payload)
      toast.success(`Author ${nextStatus === 'active' ? 'activated' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/authors/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this author. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deleteAuthor(id)
      toast.success('Author deleted.')
      navigate('/admin/authors')
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'This author is credited on articles and can\'t be deleted. Try archiving instead.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the author editor" description={loadError} />
  if (notFound) return <EmptyState title="Author not found" description="This author may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Author' : `Edit: ${form.name || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/authors/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && (
              <a href={`/authors/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
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
              <Field label="Display name">
                <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Author role" hint="e.g. Staff Writer, Contributor, Editor">
                <input
                  value={form.role}
                  onChange={(e) => updateField('role', e.target.value)}
                  list="author-role-suggestions"
                  className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none"
                />
                <datalist id="author-role-suggestions">
                  {SUGGESTED_ROLES.map((r) => (
                    <option key={r} value={r} />
                  ))}
                </datalist>
              </Field>
            </div>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/authors/${form.slug || 'your-slug'}`}>
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
            <Field label="Short bio" hint="shown in article bylines and on cards">
              <textarea rows={2} value={form.shortBio} onChange={(e) => updateField('shortBio', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Biography" description="The full profile biography shown on the public author page.">
            <ArticleBlockEditor blocks={form.bio} onChange={(bio) => updateField('bio', bio)} />
          </Section>

          <Section title="Profile image">
            <MediaPicker label="Portrait" aspect={1} value={form.photoMedia} onChange={(media) => updateField('photoMedia', media)} />
          </Section>

          <Section title="Linked person" description="Only set this if the same human is also profiled as a Person — most authors won't have one.">
            <Field label="Person profile" hint="optional">
              <select value={form.personId} onChange={(e) => updateField('personId', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} {p.status !== 'published' ? `(${p.status})` : ''}
                  </option>
                ))}
              </select>
            </Field>
          </Section>

          <Section title="Editorial role / expertise" description="What this author writes about — uses the existing Topic taxonomy.">
            <div className="flex flex-wrap gap-2">
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
              {topics.length === 0 && <p className="text-xs text-charcoal-600/70">No topics exist yet.</p>}
            </div>
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
              <Field label="City / location" hint="optional">
                <input value={form.location} onChange={(e) => updateField('location', e.target.value)} placeholder="Lagos, Nigeria" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
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
            <Field label="SEO title" hint="falls back to the author's name">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the short bio">
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

            {hasNoBio && (
              <div className="mt-4 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add a short bio or biography before activating.</span>
              </div>
            )}

            <div className="mt-4 space-y-2">
              <button type="button" onClick={() => handleSave('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                <Save size={13} /> {saving ? 'Saving…' : 'Save draft'}
              </button>
              <button type="button" onClick={() => handleSave('active')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                Activate
              </button>
              {!isNew && form.status !== 'archived' && (
                <button type="button" onClick={() => handleSave('archived')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  <Archive size={13} /> Archive
                </button>
              )}
              {!isNew && (
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  <Trash2 size={13} className="mr-1 inline" /> Delete author
                </button>
              )}
            </div>
          </div>

          <Link to="/admin/authors" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all authors
          </Link>
        </div>
      </div>
    </div>
  )
}
