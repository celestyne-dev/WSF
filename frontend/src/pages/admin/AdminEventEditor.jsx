import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, AlertTriangle, Archive, Trash2 } from 'lucide-react'
import { fetchEventBySlug, createEvent, updateEvent, deleteEvent } from '../../api/events'
import { fetchOrganizations } from '../../api/taxonomies'
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

const STATUSES = ['draft', 'published', 'cancelled', 'archived']
const TYPES = [
  'Conference',
  'Summit',
  'Workshop',
  'Webinar',
  'Networking Event',
  'Panel',
  'Masterclass',
  'Training',
  'Community Event',
  'Career Event',
  'Founder Event',
  'Mentorship Event',
  'Awards Event',
  'Other',
]
const FORMATS = [
  { value: 'in-person', label: 'In person' },
  { value: 'virtual', label: 'Virtual' },
  { value: 'hybrid', label: 'Hybrid' },
]
// A representative spread of IANA zones across every region — not
// exhaustive (any valid IANA identifier can still be typed), just enough
// to make the common cases a click instead of free typing, without
// defaulting anyone to one region's time.
const COMMON_TIMEZONES = [
  'Africa/Nairobi',
  'Africa/Lagos',
  'Africa/Johannesburg',
  'Africa/Cairo',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Sao_Paulo',
  'America/Mexico_City',
  'America/Bogota',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Madrid',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Manila',
  'Asia/Shanghai',
  'Australia/Sydney',
  'Pacific/Auckland',
  'UTC',
]

function blankForm() {
  return {
    title: '',
    slug: '',
    shortDescription: '',
    description: [],
    type: '',
    format: '',
    date: '',
    endDate: '',
    startTime: '',
    endTime: '',
    timezone: '',
    location: '',
    address: '',
    countryCode: '',
    venue: '',
    virtualLink: '',
    virtualLinkPublic: false,
    organizerId: '',
    organizerName: '',
    speakerSlugs: [],
    sponsorSlugs: [],
    registrationUrl: '',
    registrationRequired: true,
    registrationDeadline: '',
    registrationInstructions: '',
    soldOut: false,
    ticketPrice: '',
    currency: '',
    capacity: '',
    coverMedia: null,
    status: 'draft',
    featured: false,
    sponsored: false,
    seoTitle: '',
    seoDescription: '',
    seoCanonical: '',
    seoOgMedia: null,
  }
}

function toForm(event) {
  return {
    title: event.title || '',
    slug: event.slug || '',
    shortDescription: event.shortDescription || '',
    description: event.description || [],
    type: event.type || '',
    format: event.format || '',
    date: event.date || '',
    endDate: event.endDate || '',
    startTime: event.startTime || '',
    endTime: event.endTime || '',
    timezone: event.timezone || '',
    location: event.location || '',
    address: event.address || '',
    countryCode: event.countryCode || '',
    venue: event.venue || '',
    virtualLink: event.virtualLink || '',
    virtualLinkPublic: !!event.virtualLinkPublic,
    organizerId: event.organizerId || '',
    organizerName: event.organizer || '',
    speakerSlugs: event.speakers || [],
    sponsorSlugs: event.sponsors || [],
    registrationUrl: event.registrationUrl || '',
    registrationRequired: event.registrationRequired !== false,
    registrationDeadline: event.registrationDeadline || '',
    registrationInstructions: event.registrationInstructions || '',
    soldOut: !!event.soldOut,
    ticketPrice: event.ticketPrice ?? '',
    currency: event.currency || '',
    capacity: event.capacity ?? '',
    coverMedia: event.coverMedia || null,
    status: event.status || 'draft',
    featured: !!event.featured,
    sponsored: !!event.sponsored,
    seoTitle: event.seo?.title || '',
    seoDescription: event.seo?.description || '',
    seoCanonical: event.seo?.canonical || '',
    seoOgMedia: event.seo?.ogImageMediaId ? { id: event.seo.ogImageMediaId } : null,
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

export default function AdminEventEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id

  const [organizations, setOrganizations] = useState([])
  const [countries, setCountries] = useState([])
  const [people, setPeople] = useState([])
  const [speakerSearch, setSpeakerSearch] = useState('')
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
      fetchPeople({ pageSize: 200 }),
      isNew ? Promise.resolve(null) : fetchEventBySlug(id),
    ])
      .then(([orgRes, countryList, peopleRes, existing]) => {
        if (!active) return
        setOrganizations(orgRes.items)
        setCountries([...countryList].sort((a, b) => a.name.localeCompare(b.name)))
        setPeople(peopleRes.items)
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the event editor. Please try again.'))
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
      if (field === 'organizerId' && value) {
        const org = organizations.find((o) => String(o.id) === String(value))
        if (org && !prev.organizerName) next.organizerName = org.name
      }
      if (field === 'format' && value !== 'in-person' && value !== 'hybrid') {
        // keep venue/address as-is; only format visibility changes
      }
      return next
    })
  }

  function toggleSpeaker(slug) {
    setForm((prev) => ({
      ...prev,
      speakerSlugs: prev.speakerSlugs.includes(slug) ? prev.speakerSlugs.filter((s) => s !== slug) : [...prev.speakerSlugs, slug],
    }))
  }

  function validateSlug(slug) {
    if (!slug) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as an event slug.`
    return null
  }

  const selectedOrg = organizations.find((o) => String(o.id) === String(form?.organizerId))
  const hasNoDescription = form && form.description.length === 0
  const hasNoRegistrationUrl = form && form.registrationRequired && !form.registrationUrl
  const showLocation = form && (form.format === 'in-person' || form.format === 'hybrid' || !form.format)
  const showVirtual = form && (form.format === 'virtual' || form.format === 'hybrid')
  const endDateInvalid = form && form.endDate && form.date && form.endDate < form.date
  const endTimeInvalid = form && !form.endDate && form.startTime && form.endTime && form.endTime < form.startTime
  const registrationDeadlineInvalid = form && form.registrationDeadline && (form.endDate || form.date) && form.registrationDeadline > (form.endDate || form.date)
  const filteredPeople = people.filter((p) => p.name.toLowerCase().includes(speakerSearch.toLowerCase()))

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (!form.date) {
      toast.error('Set a start date.')
      return
    }
    if (endDateInvalid) {
      toast.error('End date cannot be before the start date.')
      return
    }
    if (endTimeInvalid) {
      toast.error('End time cannot be before the start time.')
      return
    }
    if (registrationDeadlineInvalid) {
      toast.error('Registration deadline should be on or before the event date.')
      return
    }
    if (nextStatus === 'published') {
      if (hasNoDescription) {
        toast.error('Add an event description before publishing.')
        return
      }
      if (hasNoRegistrationUrl) {
        toast.error('Add a registration URL before publishing — WSF never shows a fake Register button.')
        return
      }
    }
    setErrors({})
    setSaving(true)

    const payload = {
      title: form.title,
      slug: form.slug,
      shortDescription: form.shortDescription || null,
      description: form.description,
      type: form.type || null,
      format: form.format || null,
      date: form.date,
      endDate: form.endDate || null,
      startTime: form.startTime || null,
      endTime: form.endTime || null,
      timezone: form.timezone || null,
      location: form.location || null,
      address: form.address || null,
      countryCode: form.countryCode || null,
      venue: form.venue || null,
      virtualLink: form.virtualLink || null,
      virtualLinkPublic: form.virtualLinkPublic,
      organizerId: form.organizerId || null,
      organizerName: form.organizerName || selectedOrg?.name || null,
      speakerSlugs: form.speakerSlugs,
      sponsorSlugs: form.sponsorSlugs,
      registrationUrl: form.registrationUrl || null,
      registrationRequired: form.registrationRequired,
      registrationDeadline: form.registrationDeadline || null,
      registrationInstructions: form.registrationInstructions || null,
      soldOut: form.soldOut,
      ticketPrice: form.ticketPrice === '' ? null : Number(form.ticketPrice),
      currency: form.currency || null,
      capacity: form.capacity === '' ? null : Number(form.capacity),
      coverMediaId: form.coverMedia?.id || null,
      status: nextStatus,
      featured: form.featured,
      sponsored: form.sponsored,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
        canonical: form.seoCanonical || null,
        ogImageMediaId: form.seoOgMedia?.id || null,
      },
    }

    try {
      const saved = isNew ? await createEvent(payload) : await updateEvent(id, payload)
      toast.success(`Event ${nextStatus === 'published' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/events/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this event. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.title}? This can't be undone.`)) return
    try {
      await deleteEvent(id)
      toast.success('Event deleted.')
      navigate('/admin/events')
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong deleting this event.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the event editor" description={loadError} />
  if (notFound) return <EmptyState title="Event not found" description="This event may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Event' : `Edit: ${form.title || 'Untitled'}`}
        description="Public URL: womenshapingfutures.org/events/{slug}"
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.slug && (
              <a href={`/events/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Event title">
              <input value={form.title} onChange={(e) => updateField('title', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL: womenshapingfutures.org/events/${form.slug || 'your-slug'}`}>
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
            <Field label="Short summary" hint="shown on event cards">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Event type">
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

          <Section title="Description" description="Structure the content however makes sense — About the event, Who should attend, Agenda, What attendees will gain — you decide the headings.">
            <ArticleBlockEditor blocks={form.description} onChange={(description) => updateField('description', description)} />
          </Section>

          <Section title="Date, time &amp; timezone">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Start date">
                <input type="date" value={form.date} onChange={(e) => updateField('date', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
              </Field>
              <Field label="End date" hint="only set this for multi-day events">
                <input type="date" value={form.endDate} onChange={(e) => updateField('endDate', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
              </Field>
            </div>
            {endDateInvalid && <p className="text-xs text-rose-600">End date can't be before the start date.</p>}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Start time" hint="optional">
                <input type="time" value={form.startTime} onChange={(e) => updateField('startTime', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
              </Field>
              <Field label="End time" hint="optional">
                <input type="time" value={form.endTime} onChange={(e) => updateField('endTime', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
              </Field>
            </div>
            {endTimeInvalid && <p className="text-xs text-rose-600">End time can't be before the start time.</p>}
            <Field label="Timezone" hint="IANA identifier, e.g. Africa/Nairobi, America/New_York, Asia/Singapore">
              <input list="event-timezones" value={form.timezone} onChange={(e) => updateField('timezone', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              <datalist id="event-timezones">
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz} value={tz} />
                ))}
              </datalist>
            </Field>
          </Section>

          <Section title="Event format">
            <Field label="Format">
              <select value={form.format} onChange={(e) => updateField('format', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </Field>
          </Section>

          {(showLocation || showVirtual) && (
            <Section title="Location">
              {showLocation && (
                <>
                  <Field label="Venue" hint="optional">
                    <input value={form.venue} onChange={(e) => updateField('venue', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
                  </Field>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <Field label="City / location" hint="optional">
                      <input value={form.location} onChange={(e) => updateField('location', e.target.value)} placeholder="Nairobi, Kenya" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
                    </Field>
                    <Field label="Country" hint="optional">
                      <select value={form.countryCode} onChange={(e) => updateField('countryCode', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                        <option value="">— None —</option>
                        {countries.map((c) => (
                          <option key={c.code} value={c.code}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <Field label="Street address" hint="optional">
                    <input value={form.address} onChange={(e) => updateField('address', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
                  </Field>
                </>
              )}
              {showVirtual && (
                <>
                  <Field label="Virtual joining link" hint="registered attendees only, unless made public below">
                    <input value={form.virtualLink} onChange={(e) => updateField('virtualLink', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
                  </Field>
                  <label className="flex items-center gap-2 text-sm text-charcoal-600">
                    <input type="checkbox" checked={form.virtualLinkPublic} onChange={(e) => updateField('virtualLinkPublic', e.target.checked)} />
                    Show this link publicly on the event page (leave unchecked to send it only to registered attendees)
                  </label>
                </>
              )}
            </Section>
          )}

          <Section title="Host / organizer" description="Use an existing Organization wherever possible — its logo and profile are reused automatically. Leave both blank for events hosted directly by Women Shaping Futures.">
            <Field label="Organization" hint="optional">
              <select value={form.organizerId} onChange={(e) => updateField('organizerId', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                <option value="">— None —</option>
                {organizations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} {o.status !== 'published' ? `(${o.status})` : ''}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Host name" hint={selectedOrg ? 'auto-filled from the selected organization — override if needed' : 'optional — defaults to Women Shaping Futures on the public page when blank'}>
              <input value={form.organizerName} onChange={(e) => updateField('organizerName', e.target.value)} placeholder={selectedOrg?.name || 'Women Shaping Futures'} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Speakers" description="Searchable — pulled from published People profiles.">
            <input value={speakerSearch} onChange={(e) => setSpeakerSearch(e.target.value)} placeholder="Search people…" className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
            <div className="flex max-h-56 flex-wrap gap-1.5 overflow-y-auto border border-taupe-200 p-3">
              {filteredPeople.map((p) => (
                <button
                  key={p.slug}
                  type="button"
                  onClick={() => toggleSpeaker(p.slug)}
                  className={`px-2.5 py-1 text-xs font-medium ${form.speakerSlugs.includes(p.slug) ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Registration">
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.registrationRequired} onChange={(e) => updateField('registrationRequired', e.target.checked)} />
              Registration required
            </label>
            <Field label="Registration URL" hint="where WSF sends attendees to register">
              <input value={form.registrationUrl} onChange={(e) => updateField('registrationUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Registration deadline" hint="optional">
              <input type="date" value={form.registrationDeadline} onChange={(e) => updateField('registrationDeadline', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm" />
            </Field>
            {registrationDeadlineInvalid && <p className="text-xs text-rose-600">Registration deadline should be on or before the event date.</p>}
            <Field label="Registration instructions" hint="optional — shown alongside the Register button">
              <textarea rows={2} value={form.registrationInstructions} onChange={(e) => updateField('registrationInstructions', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Capacity" hint="optional">
              <input type="number" value={form.capacity} onChange={(e) => updateField('capacity', e.target.value)} className="w-32 border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <label className="flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.soldOut} onChange={(e) => updateField('soldOut', e.target.checked)} />
              Sold out / full
            </label>
          </Section>

          <Section title="Pricing" description="Leave blank for a free event.">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Ticket price" hint="optional — leave blank if free">
                <input type="number" value={form.ticketPrice} onChange={(e) => updateField('ticketPrice', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Currency" hint="ISO code, e.g. USD, KES, EUR">
                <input value={form.currency} onChange={(e) => updateField('currency', e.target.value.toUpperCase().slice(0, 3))} className="w-full border border-taupe-300 px-3 py-2.5 text-sm uppercase focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="Media">
            <MediaPicker label="Hero / featured image" aspect={2.6} value={form.coverMedia} onChange={(media) => updateField('coverMedia', media)} />
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the event title">
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
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
            <select value={form.status} onChange={(e) => updateField('status', e.target.value)} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>

            {hasNoDescription && (
              <div className="mt-3 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add an event description before publishing.</span>
              </div>
            )}
            {hasNoRegistrationUrl && (
              <div className="mt-3 flex gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>Add a registration URL before publishing, or mark registration as not required.</span>
              </div>
            )}

            <div className="mt-4 space-y-2">
              <button type="button" onClick={() => handleSave('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                <Save size={13} /> {saving ? 'Saving…' : 'Save draft'}
              </button>
              <button type="button" onClick={() => handleSave('published')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                Publish
              </button>
              {!isNew && form.status !== 'cancelled' && (
                <button type="button" onClick={() => handleSave('cancelled')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  Cancel event
                </button>
              )}
              {!isNew && form.status !== 'archived' && (
                <button type="button" onClick={() => handleSave('archived')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  <Archive size={13} /> Archive
                </button>
              )}
              {!isNew && (
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  <Trash2 size={13} className="mr-1 inline" /> Delete event
                </button>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Featured / sponsored</p>
            <p className="mt-1 text-xs text-charcoal-600/70">CMS readiness only — no payment or sponsorship packages in this release.</p>
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

          <Link to="/admin/events" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all events
          </Link>
        </div>
      </div>
    </div>
  )
}
