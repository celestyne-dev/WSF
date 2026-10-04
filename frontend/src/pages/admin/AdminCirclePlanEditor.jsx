import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, Archive, Trash2, Plus, X } from 'lucide-react'
import { fetchAdminCirclePlan, createCirclePlan, updateCirclePlan, deleteCirclePlan } from '../../api/circle'
import { RESERVED_SLUGS } from '../../constants/routes'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
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
const BILLING_INTERVALS = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
]

function blankForm() {
  return {
    name: '',
    slug: '',
    shortDescription: '',
    description: [],
    billingInterval: 'monthly',
    price: '',
    currency: '',
    status: 'draft',
    featured: false,
    displayOrder: 0,
    checkoutUrl: '',
    manageBillingUrl: '',
    benefits: [],
    seoTitle: '',
    seoDescription: '',
  }
}

function toForm(plan) {
  return {
    name: plan.name || '',
    slug: plan.slug || '',
    shortDescription: plan.shortDescription || '',
    description: plan.description || [],
    billingInterval: plan.billingInterval || 'monthly',
    price: plan.price ?? '',
    currency: plan.currency || '',
    status: plan.status || 'draft',
    featured: !!plan.featured,
    displayOrder: plan.displayOrder ?? 0,
    checkoutUrl: plan.checkoutUrl || '',
    manageBillingUrl: plan.manageBillingUrl || '',
    benefits: plan.benefits || [],
    seoTitle: plan.seo?.title || '',
    seoDescription: plan.seo?.description || '',
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

export default function AdminCirclePlanEditor() {
  const { id: slug } = useParams()
  const navigate = useNavigate()
  const isNew = !slug

  const [form, setForm] = useState(undefined)
  const [newBenefit, setNewBenefit] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    if (isNew) {
      setForm(blankForm())
      return undefined
    }
    let active = true
    fetchAdminCirclePlan(slug)
      .then((existing) => {
        if (!active) return
        if (existing) setForm(toForm(existing))
        else setNotFound(true)
      })
      .catch(() => active && setLoadError('Something went wrong loading this plan. Please try again.'))
    return () => {
      active = false
    }
  }, [slug, isNew])

  function updateField(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'name' && !slugTouched) {
        next.slug = slugify(value)
      }
      return next
    })
  }

  function addBenefit() {
    if (!newBenefit.trim()) return
    setForm((prev) => ({ ...prev, benefits: [...prev.benefits, newBenefit.trim()] }))
    setNewBenefit('')
  }

  function removeBenefit(index) {
    setForm((prev) => ({ ...prev, benefits: prev.benefits.filter((_, i) => i !== index) }))
  }

  function validateSlug(value) {
    if (!value) return 'Slug is required.'
    if (RESERVED_SLUGS.includes(value)) return `"${value}" is a reserved system route and cannot be used as a plan slug.`
    return null
  }

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (!form.name) {
      toast.error('Add a plan name.')
      return
    }
    if (form.price === '' || Number(form.price) < 0) {
      toast.error('Set a price of 0 or more.')
      return
    }
    if (!/^[A-Z]{3}$/.test(form.currency)) {
      toast.error('Currency must be exactly 3 uppercase letters (e.g. USD).')
      return
    }
    setErrors({})
    setSaving(true)

    const payload = {
      name: form.name,
      slug: form.slug,
      shortDescription: form.shortDescription || null,
      description: form.description,
      billingInterval: form.billingInterval,
      price: form.price,
      currency: form.currency,
      status: nextStatus,
      featured: form.featured,
      displayOrder: form.displayOrder,
      checkoutUrl: form.checkoutUrl || null,
      manageBillingUrl: form.manageBillingUrl || null,
      benefits: form.benefits,
      seo: {
        title: form.seoTitle || null,
        description: form.seoDescription || null,
      },
    }

    try {
      const saved = isNew ? await createCirclePlan(payload) : await updateCirclePlan(slug, payload)
      toast.success(`Plan ${nextStatus === 'active' ? 'published' : 'saved'} as ${nextStatus}.`)
      if (isNew) navigate(`/admin/circle/plans/${saved.slug}`)
      else setForm(toForm(saved))
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong saving this plan. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${form.name}? This can't be undone.`)) return
    try {
      await deleteCirclePlan(slug)
      toast.success('Plan deleted.')
      navigate('/admin/circle/plans')
    } catch (err) {
      const message = err?.response?.data?.error?.message || err?.apiError?.message || 'Something went wrong deleting this plan.'
      toast.error(message)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the plan editor" description={loadError} />
  if (notFound) return <EmptyState title="Plan not found" description="This plan may have been deleted or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New WSF Circle Plan' : `Edit: ${form.name || 'Untitled'}`}
        description="Shown on the public /circle page when active."
        actions={
          <>
            <StatusBadge status={form.status} />
            {!isNew && form.status === 'active' && (
              <a href="/circle" target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> Preview
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Plan name">
              <input value={form.name} onChange={(e) => updateField('name', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint={`public URL references: ${form.slug || 'your-slug'}`}>
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
            <Field label="Short description" hint="shown on the plan card">
              <textarea rows={2} value={form.shortDescription} onChange={(e) => updateField('shortDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Description" description="Optional — structure the content however makes sense.">
            <ArticleBlockEditor blocks={form.description} onChange={(description) => updateField('description', description)} />
          </Section>

          <Section title="Benefits" description="Short, broad lines — never a specific claim about a feature that doesn't exist yet.">
            <div className="space-y-2">
              {form.benefits.map((b, i) => (
                <div key={i} className="flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                  <span>{b}</span>
                  <button type="button" onClick={() => removeBenefit(i)} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Remove">
                    <X size={15} />
                  </button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={newBenefit}
                onChange={(e) => setNewBenefit(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addBenefit()
                  }
                }}
                placeholder="Add a benefit…"
                className="flex-1 border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
              />
              <button type="button" onClick={addBenefit} className="btn-secondary !px-3 !py-2 text-xs">
                <Plus size={13} /> Add
              </button>
            </div>
          </Section>

          <Section title="Pricing">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Billing interval">
                <select value={form.billingInterval} onChange={(e) => updateField('billingInterval', e.target.value)} className="w-full border border-taupe-300 px-3 py-2 text-sm">
                  {BILLING_INTERVALS.map((b) => (
                    <option key={b.value} value={b.value}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Price" hint="whole units, e.g. 1000 = $10.00 if USD treats it as cents — follow your own currency's convention">
                <input type="number" min="0" value={form.price} onChange={(e) => updateField('price', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Currency" hint="ISO code, e.g. USD, KES, EUR">
                <input value={form.currency} onChange={(e) => updateField('currency', e.target.value.toUpperCase().slice(0, 3))} className="w-full border border-taupe-300 px-3 py-2.5 text-sm uppercase focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section
            title="Checkout / billing"
            description="No payment gateway is wired up yet. Leave Checkout URL blank to show a professional 'enrollment coming soon' state instead of a broken button."
          >
            <Field label="Checkout URL" hint="external secure checkout — https:// only">
              <input value={form.checkoutUrl} onChange={(e) => updateField('checkoutUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Manage billing URL" hint="optional — a future payment provider's customer portal">
              <input value={form.manageBillingUrl} onChange={(e) => updateField('manageBillingUrl', e.target.value)} placeholder="https://…" className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="SEO">
            <Field label="SEO title" hint="falls back to the plan name">
              <input value={form.seoTitle} onChange={(e) => updateField('seoTitle', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Meta description" hint="falls back to the short description">
              <textarea rows={2} value={form.seoDescription} onChange={(e) => updateField('seoDescription', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
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

            <div className="mt-4 space-y-2">
              <button type="button" onClick={() => handleSave('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                <Save size={13} /> {saving ? 'Saving…' : 'Save draft'}
              </button>
              <button type="button" onClick={() => handleSave('active')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                Publish
              </button>
              {!isNew && form.status !== 'archived' && (
                <button type="button" onClick={() => handleSave('archived')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                  <Archive size={13} /> Archive
                </button>
              )}
              {!isNew && (
                <button type="button" onClick={handleDelete} className="w-full py-2 text-xs font-semibold text-rose-600 hover:underline">
                  <Trash2 size={13} className="mr-1 inline" /> Delete plan
                </button>
              )}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Featured</p>
            <p className="mt-1 text-xs text-charcoal-600/70">Highlights this plan on the public /circle page.</p>
            <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
              <input type="checkbox" checked={form.featured} onChange={(e) => updateField('featured', e.target.checked)} />
              Featured
            </label>
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Display order</p>
            <input
              type="number"
              value={form.displayOrder}
              onChange={(e) => updateField('displayOrder', Number(e.target.value))}
              className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
            />
          </div>

          <Link to="/admin/circle/plans" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all plans
          </Link>
        </div>
      </div>
    </div>
  )
}
