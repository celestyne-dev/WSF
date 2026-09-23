import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { Save, Eye, EyeOff, Plus, X, Pencil } from 'lucide-react'
import {
  fetchAdvertisePage,
  updateAdvertisePage,
  updateAdvertisePageStatus,
  fetchAdvertiseMetrics,
  createAdvertiseMetric,
  updateAdvertiseMetric,
  deleteAdvertiseMetric,
  fetchAdvertiseOfferings,
  createAdvertiseOffering,
  updateAdvertiseOffering,
  deleteAdvertiseOffering,
  fetchAdvertiseHistory,
} from '../../api/advertise'
import { ADVERTISE_OFFERING_STATUSES, ADVERTISE_PRICING_MODES, ADVERTISE_PRICING_MODE_LABELS } from '../../constants/advertise'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import MediaPicker from '../../components/cms/MediaPicker'
import ArticleBlockEditor from '../../components/cms/ArticleBlockEditor'
import { formatDate } from '../../utils/format'
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

function blankMetricForm() {
  return { label: '', value: '', unit: '', sourceNote: '', asOfDate: '', displayOrder: 0, publicVisible: true }
}

function metricToForm(m) {
  return { label: m.label, value: m.value, unit: m.unit, sourceNote: m.sourceNote, asOfDate: m.asOfDate, displayOrder: m.displayOrder, publicVisible: m.publicVisible }
}

function blankOfferingForm() {
  return {
    name: '', shortDescription: '', fullDescription: '', features: [], ctaLabel: '', displayOrder: 0,
    featured: false, status: 'active', pricingMode: 'contact', priceAmount: '', currency: '', pricingNote: '',
  }
}

function offeringToForm(o) {
  return {
    name: o.name, shortDescription: o.shortDescription, fullDescription: o.fullDescription, features: o.features,
    ctaLabel: o.ctaLabel, displayOrder: o.displayOrder, featured: o.featured, status: o.status,
    pricingMode: o.pricingMode, priceAmount: o.priceAmount ?? '', currency: o.currency, pricingNote: o.pricingNote,
  }
}

export default function AdminAdvertise() {
  const [page, setPage] = useState(null)
  const [form, setForm] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [offerings, setOfferings] = useState(null)
  const [history, setHistory] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)

  const [metricFormId, setMetricFormId] = useState(null) // null = closed, 'new' = create, or metric id
  const [metricForm, setMetricForm] = useState(blankMetricForm())
  const [savingMetric, setSavingMetric] = useState(false)

  const [offeringFormId, setOfferingFormId] = useState(null)
  const [offeringForm, setOfferingForm] = useState(blankOfferingForm())
  const [savingOffering, setSavingOffering] = useState(false)

  function load() {
    let active = true
    Promise.all([fetchAdvertisePage(), fetchAdvertiseMetrics(), fetchAdvertiseOfferings(), fetchAdvertiseHistory()])
      .then(([pageRes, metricsRes, offeringsRes, historyRes]) => {
        if (!active) return
        setPage(pageRes)
        setForm(pageRes)
        setMetrics(metricsRes)
        setOfferings(offeringsRes)
        setHistory(historyRes)
      })
      .catch(() => {
        if (!active) return
        setLoadError('Something went wrong loading the Advertise page. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [])

  async function handleSavePage() {
    setSaving(true)
    try {
      const updated = await updateAdvertisePage(form)
      setPage(updated)
      setForm(updated)
      toast.success('Advertise page updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving the page.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateAdvertisePageStatus(status)
      setPage(updated)
      setForm(updated)
      toast.success(status === 'published' ? 'Advertise page is now live.' : 'Advertise page unpublished.')
      fetchAdvertiseHistory().then(setHistory)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
    }
  }

  function handleAddFaq() {
    setForm({ ...form, faq: [...form.faq, { question: '', answer: '' }] })
  }
  function handleFaqChange(index, key, value) {
    const faq = form.faq.map((f, i) => (i === index ? { ...f, [key]: value } : f))
    setForm({ ...form, faq })
  }
  function handleRemoveFaq(index) {
    setForm({ ...form, faq: form.faq.filter((_, i) => i !== index) })
  }

  // Metrics ------------------------------------------------------------
  function openMetricForm(metric) {
    if (metric) {
      setMetricFormId(metric.id)
      setMetricForm(metricToForm(metric))
    } else {
      setMetricFormId('new')
      setMetricForm(blankMetricForm())
    }
  }

  async function handleSaveMetric() {
    setSavingMetric(true)
    try {
      if (metricFormId === 'new') {
        const created = await createAdvertiseMetric(metricForm)
        setMetrics([...metrics, created].sort((a, b) => a.displayOrder - b.displayOrder))
        toast.success('Metric added.')
      } else {
        const updated = await updateAdvertiseMetric(metricFormId, metricForm)
        setMetrics(metrics.map((m) => (m.id === updated.id ? updated : m)).sort((a, b) => a.displayOrder - b.displayOrder))
        toast.success('Metric updated.')
      }
      setMetricFormId(null)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this metric.')
    } finally {
      setSavingMetric(false)
    }
  }

  async function handleDeleteMetric(id) {
    try {
      await deleteAdvertiseMetric(id)
      setMetrics(metrics.filter((m) => m.id !== id))
      toast.success('Metric removed.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong removing this metric.')
    } finally {
      setConfirmAction(null)
    }
  }

  // Offerings ------------------------------------------------------------
  function openOfferingForm(offering) {
    if (offering) {
      setOfferingFormId(offering.id)
      setOfferingForm(offeringToForm(offering))
    } else {
      setOfferingFormId('new')
      setOfferingForm(blankOfferingForm())
    }
  }

  async function handleSaveOffering() {
    setSavingOffering(true)
    try {
      if (offeringFormId === 'new') {
        const created = await createAdvertiseOffering(offeringForm)
        setOfferings([...offerings, created].sort((a, b) => a.displayOrder - b.displayOrder))
        toast.success('Offering added.')
      } else {
        const updated = await updateAdvertiseOffering(offeringFormId, offeringForm)
        setOfferings(offerings.map((o) => (o.id === updated.id ? updated : o)).sort((a, b) => a.displayOrder - b.displayOrder))
        toast.success('Offering updated.')
      }
      setOfferingFormId(null)
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving this offering.')
    } finally {
      setSavingOffering(false)
    }
  }

  async function handleDeleteOffering(id) {
    try {
      await deleteAdvertiseOffering(id)
      setOfferings(offerings.filter((o) => o.id !== id))
      toast.success('Offering removed.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong removing this offering.')
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the Advertise page" description={loadError} />
  if (form === null || metrics === null || offerings === null) return <PageLoader />

  const offeringNeedsPrice = offeringForm.pricingMode === 'starting_from' || offeringForm.pricingMode === 'fixed'

  return (
    <div>
      <AdminPageHeader
        title="Advertise / Media Kit"
        description="Manages the public /advertise page — hero, audience metrics, offerings, media kit, and FAQ. Advertising inquiries are handled in Partnerships (filter by type)."
        actions={page && <StatusBadge status={page.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {/* Hero */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Hero</p>
            <div className="grid grid-cols-1 gap-4">
              <Field label="Heading">
                <input value={form.heroHeading} onChange={(e) => setForm({ ...form, heroHeading: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Description">
                <textarea rows={2} value={form.heroDescription} onChange={(e) => setForm({ ...form, heroDescription: e.target.value })} className={inputClass} />
              </Field>
              <MediaPicker label="Hero media (optional)" value={form.heroMedia} onChange={(m) => setForm({ ...form, heroMedia: m })} aspect={16 / 9} />
            </div>
          </div>

          {/* Introduction */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Introduction</p>
            <ArticleBlockEditor blocks={form.introContent} onChange={(introContent) => setForm({ ...form, introContent })} />
          </div>

          {/* Audience */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Audience overview</p>
            <Field label="Overview text" hint="describe the audience honestly — no invented reach claims">
              <textarea rows={3} value={form.audienceOverview} onChange={(e) => setForm({ ...form, audienceOverview: e.target.value })} className={inputClass} />
            </Field>
          </div>

          {/* Audience metrics */}
          <div className="border border-taupe-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Audience metrics</p>
              <button type="button" onClick={() => openMetricForm(null)} className="btn-secondary !px-3 !py-1.5 text-xs">
                <Plus size={14} /> Add metric
              </button>
            </div>
            <p className="mt-1 text-xs text-charcoal-600/60">Real, sourced figures only. "Source note" and "as-of date" are internal — never shown publicly.</p>

            <div className="mt-3 space-y-2">
              {metrics.length === 0 && <p className="text-sm text-charcoal-600/60">No metrics yet.</p>}
              {metrics.map((m) => (
                <div key={m.id} className="flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                  <div>
                    <span className="font-medium text-charcoal">{m.label}</span>
                    <span className="ml-2 text-charcoal-600">{m.value} {m.unit}</span>
                    {!m.publicVisible && <span className="ml-2 text-xs text-charcoal-600/60">(hidden)</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={() => openMetricForm(m)} className="text-charcoal-600/60 hover:text-burgundy-600" aria-label="Edit metric">
                      <Pencil size={14} />
                    </button>
                    <button type="button" onClick={() => setConfirmAction({ type: 'deleteMetric', id: m.id, label: m.label })} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Remove metric">
                      <X size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {metricFormId !== null && (
              <div className="mt-4 border border-taupe-300 bg-taupe-50 p-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">{metricFormId === 'new' ? 'New metric' : 'Edit metric'}</p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field label="Label">
                    <input value={metricForm.label} onChange={(e) => setMetricForm({ ...metricForm, label: e.target.value })} className={inputClass} />
                  </Field>
                  <Field label="Value" hint="free text, e.g. 132,000+">
                    <input value={metricForm.value} onChange={(e) => setMetricForm({ ...metricForm, value: e.target.value })} className={inputClass} />
                  </Field>
                  <Field label="Unit" hint="optional">
                    <input value={metricForm.unit} onChange={(e) => setMetricForm({ ...metricForm, unit: e.target.value })} className={inputClass} />
                  </Field>
                  <Field label="As-of date" hint="optional">
                    <input type="date" value={metricForm.asOfDate || ''} onChange={(e) => setMetricForm({ ...metricForm, asOfDate: e.target.value })} className={inputClass} />
                  </Field>
                  <Field label="Display order">
                    <input type="number" value={metricForm.displayOrder} onChange={(e) => setMetricForm({ ...metricForm, displayOrder: Number(e.target.value) })} className={inputClass} />
                  </Field>
                  <Field label="Source note" hint="internal only — where this figure came from">
                    <input value={metricForm.sourceNote} onChange={(e) => setMetricForm({ ...metricForm, sourceNote: e.target.value })} className={inputClass} />
                  </Field>
                </div>
                <label className="mt-3 flex items-center gap-2 text-sm text-charcoal-600">
                  <input type="checkbox" checked={metricForm.publicVisible} onChange={(e) => setMetricForm({ ...metricForm, publicVisible: e.target.checked })} />
                  Publicly visible
                </label>
                <div className="mt-3 flex gap-2">
                  <button type="button" onClick={handleSaveMetric} disabled={savingMetric} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
                    {savingMetric ? 'Saving…' : 'Save metric'}
                  </button>
                  <button type="button" onClick={() => setMetricFormId(null)} className="text-xs font-semibold text-charcoal-600/70 hover:text-charcoal">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Why partner */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Why partner with us</p>
            <ArticleBlockEditor blocks={form.whyContent} onChange={(whyContent) => setForm({ ...form, whyContent })} />
          </div>

          {/* Offerings */}
          <div className="border border-taupe-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Advertising &amp; collaboration offerings</p>
              <button type="button" onClick={() => openOfferingForm(null)} className="btn-secondary !px-3 !py-1.5 text-xs">
                <Plus size={14} /> Add offering
              </button>
            </div>
            <p className="mt-1 text-xs text-charcoal-600/60">Describes available opportunities — not live sponsorship inventory (see Sponsors CMS for that).</p>

            <div className="mt-3 space-y-2">
              {offerings.length === 0 && <p className="text-sm text-charcoal-600/60">No offerings yet.</p>}
              {offerings.map((o) => (
                <div key={o.id} className="flex items-center justify-between border border-taupe-200 px-3 py-2 text-sm">
                  <div>
                    <span className="font-medium text-charcoal">{o.name}</span>
                    <span className="ml-2 text-xs text-charcoal-600/60">{o.status}{o.featured ? ' · featured' : ''}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={() => openOfferingForm(o)} className="text-charcoal-600/60 hover:text-burgundy-600" aria-label="Edit offering">
                      <Pencil size={14} />
                    </button>
                    <button type="button" onClick={() => setConfirmAction({ type: 'deleteOffering', id: o.id, label: o.name })} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Remove offering">
                      <X size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {offeringFormId !== null && (
              <div className="mt-4 border border-taupe-300 bg-taupe-50 p-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">{offeringFormId === 'new' ? 'New offering' : 'Edit offering'}</p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field label="Name">
                    <input value={offeringForm.name} onChange={(e) => setOfferingForm({ ...offeringForm, name: e.target.value })} className={inputClass} />
                  </Field>
                  <Field label="CTA label" hint="optional">
                    <input value={offeringForm.ctaLabel} onChange={(e) => setOfferingForm({ ...offeringForm, ctaLabel: e.target.value })} className={inputClass} />
                  </Field>
                </div>
                <div className="mt-3">
                  <Field label="Short description" hint="optional">
                    <textarea rows={2} value={offeringForm.shortDescription} onChange={(e) => setOfferingForm({ ...offeringForm, shortDescription: e.target.value })} className={inputClass} />
                  </Field>
                </div>
                <div className="mt-3">
                  <Field label="Full description" hint="optional">
                    <textarea rows={3} value={offeringForm.fullDescription} onChange={(e) => setOfferingForm({ ...offeringForm, fullDescription: e.target.value })} className={inputClass} />
                  </Field>
                </div>
                <div className="mt-3">
                  <Field label="Features" hint="one per line">
                    <textarea
                      rows={3}
                      value={offeringForm.features.join('\n')}
                      onChange={(e) => setOfferingForm({ ...offeringForm, features: e.target.value.split('\n') })}
                      className={inputClass}
                    />
                  </Field>
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <Field label="Status">
                    <select value={offeringForm.status} onChange={(e) => setOfferingForm({ ...offeringForm, status: e.target.value })} className={inputClass}>
                      {ADVERTISE_OFFERING_STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Display order">
                    <input type="number" value={offeringForm.displayOrder} onChange={(e) => setOfferingForm({ ...offeringForm, displayOrder: Number(e.target.value) })} className={inputClass} />
                  </Field>
                  <Field label="Featured">
                    <label className="flex h-[42px] items-center gap-2 text-sm text-charcoal-600">
                      <input type="checkbox" checked={offeringForm.featured} onChange={(e) => setOfferingForm({ ...offeringForm, featured: e.target.checked })} />
                      Featured
                    </label>
                  </Field>
                </div>
                <div className="mt-3 border-t border-taupe-200 pt-3">
                  <Field label="Pricing visibility">
                    <select value={offeringForm.pricingMode} onChange={(e) => setOfferingForm({ ...offeringForm, pricingMode: e.target.value })} className={inputClass}>
                      {ADVERTISE_PRICING_MODES.map((p) => (
                        <option key={p} value={p}>{ADVERTISE_PRICING_MODE_LABELS[p]}</option>
                      ))}
                    </select>
                  </Field>
                  {offeringNeedsPrice && (
                    <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <Field label="Price amount">
                        <input type="number" min="0" value={offeringForm.priceAmount} onChange={(e) => setOfferingForm({ ...offeringForm, priceAmount: e.target.value })} className={inputClass} />
                      </Field>
                      <Field label="Currency" hint="ISO code, e.g. USD — never assumed">
                        <input value={offeringForm.currency} onChange={(e) => setOfferingForm({ ...offeringForm, currency: e.target.value.toUpperCase().slice(0, 3) })} maxLength={3} className={inputClass} />
                      </Field>
                    </div>
                  )}
                  {offeringForm.pricingMode !== 'hidden' && (
                    <div className="mt-3">
                      <Field label="Pricing note" hint="optional, e.g. 'billed monthly'">
                        <input value={offeringForm.pricingNote} onChange={(e) => setOfferingForm({ ...offeringForm, pricingNote: e.target.value })} className={inputClass} />
                      </Field>
                    </div>
                  )}
                </div>
                <div className="mt-3 flex gap-2">
                  <button type="button" onClick={handleSaveOffering} disabled={savingOffering} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
                    {savingOffering ? 'Saving…' : 'Save offering'}
                  </button>
                  <button type="button" onClick={() => setOfferingFormId(null)} className="text-xs font-semibold text-charcoal-600/70 hover:text-charcoal">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Media Kit */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Media kit download</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Optional. Leave the URL blank to hide the download on the public page.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Title" hint="optional">
                <input value={form.mediaKitTitle} onChange={(e) => setForm({ ...form, mediaKitTitle: e.target.value })} className={inputClass} />
              </Field>
              <Field label="File URL" hint="hosted PDF/doc link">
                <input value={form.mediaKitUrl} onChange={(e) => setForm({ ...form, mediaKitUrl: e.target.value })} placeholder="https://" className={inputClass} />
              </Field>
              <Field label="Last updated" hint="optional">
                <input type="date" value={form.mediaKitUpdatedAt || ''} onChange={(e) => setForm({ ...form, mediaKitUpdatedAt: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* CTA + Contact */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Call to action &amp; contact</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="CTA heading">
                <input value={form.ctaHeading} onChange={(e) => setForm({ ...form, ctaHeading: e.target.value })} className={inputClass} />
              </Field>
              <Field label="CTA button label">
                <input value={form.ctaButtonLabel} onChange={(e) => setForm({ ...form, ctaButtonLabel: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="CTA description" hint="optional">
                <textarea rows={2} value={form.ctaDescription} onChange={(e) => setForm({ ...form, ctaDescription: e.target.value })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Contact email">
                <input type="email" value={form.contactEmail} onChange={(e) => setForm({ ...form, contactEmail: e.target.value })} className={inputClass} />
              </Field>
              <Field label="Contact note" hint="optional">
                <input value={form.contactNote} onChange={(e) => setForm({ ...form, contactNote: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          {/* FAQ */}
          <div className="border border-taupe-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">FAQ</p>
              <button type="button" onClick={handleAddFaq} className="btn-secondary !px-3 !py-1.5 text-xs">
                <Plus size={14} /> Add question
              </button>
            </div>
            <div className="mt-3 space-y-3">
              {form.faq.length === 0 && <p className="text-sm text-charcoal-600/60">No FAQ entries yet.</p>}
              {form.faq.map((entry, index) => (
                <div key={index} className="border border-taupe-200 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 space-y-2">
                      <input
                        value={entry.question}
                        onChange={(e) => handleFaqChange(index, 'question', e.target.value)}
                        placeholder="Question"
                        className={inputClass}
                      />
                      <textarea
                        rows={2}
                        value={entry.answer}
                        onChange={(e) => handleFaqChange(index, 'answer', e.target.value)}
                        placeholder="Answer"
                        className={inputClass}
                      />
                    </div>
                    <button type="button" onClick={() => handleRemoveFaq(index)} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Remove question">
                      <X size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* SEO */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">SEO</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Title" hint="optional">
                <input value={form.seo?.title || ''} onChange={(e) => setForm({ ...form, seo: { ...form.seo, title: e.target.value } })} className={inputClass} />
              </Field>
              <Field label="Robots" hint="optional, e.g. index,follow">
                <input value={form.seo?.robots || ''} onChange={(e) => setForm({ ...form, seo: { ...form.seo, robots: e.target.value } })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Meta description" hint="optional">
                <textarea rows={2} value={form.seo?.description || ''} onChange={(e) => setForm({ ...form, seo: { ...form.seo, description: e.target.value } })} className={inputClass} />
              </Field>
            </div>
            <p className="mt-2 text-xs text-charcoal-600/60">Canonical URL is fixed at /advertise.</p>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSavePage} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              <Save size={13} /> {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>

          {/* Activity */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Activity</p>
            {history === null && <p className="text-sm text-charcoal-600/60">Loading…</p>}
            {history !== null && history.length === 0 && <p className="text-sm text-charcoal-600/60">No activity recorded yet.</p>}
            {history !== null && history.length > 0 && (
              <ul className="space-y-2 text-sm">
                {history.map((entry) => (
                  <li key={entry.id} className="text-charcoal-600">
                    <span className="font-medium text-charcoal">{entry.action.replace('advertise.', '').replace(/_/g, ' ')}</span>
                    {entry.user && <> by {entry.user}</>}
                    <span className="text-charcoal-600/60"> &middot; {entry.createdAt ? formatDate(entry.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {/* Publishing */}
          {page && (
            <div className="border border-taupe-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
              <p className="mt-2 text-sm text-charcoal-600">
                Current status: <span className="font-semibold text-charcoal">{page.status}</span>
              </p>
              <div className="mt-4 space-y-2">
                {page.status !== 'published' && (
                  <button type="button" onClick={() => setConfirmAction({ type: 'publish' })} className="btn-secondary w-full !py-2 text-xs">
                    <Eye size={13} /> Publish
                  </button>
                )}
                {page.status === 'published' && (
                  <button type="button" onClick={() => setConfirmAction({ type: 'unpublish' })} className="btn-secondary w-full !py-2 text-xs">
                    <EyeOff size={13} /> Unpublish
                  </button>
                )}
              </div>
            </div>
          )}

          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Advertising inquiries</p>
            <p className="mt-2 text-sm text-charcoal-600">
              Submitted through the public inquiry form and stored in Partnerships — filter by type "Advertising" there.
            </p>
            <a href="/admin/partnerships?partnershipType=Advertising" className="mt-3 inline-block text-xs font-semibold text-burgundy-600 hover:underline">
              View advertising inquiries &rarr;
            </a>
          </div>
        </div>
      </div>

      {confirmAction?.type === 'publish' && (
        <ConfirmDialog
          title="Publish the Advertise page?"
          description="The page becomes visible at /advertise immediately."
          confirmLabel="Publish"
          onConfirm={() => applyStatus('published')}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction?.type === 'unpublish' && (
        <ConfirmDialog
          title="Unpublish the Advertise page?"
          description="The public /advertise page will stop rendering until republished."
          confirmLabel="Unpublish"
          danger
          onConfirm={() => applyStatus('draft')}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction?.type === 'deleteMetric' && (
        <ConfirmDialog
          title={`Remove "${confirmAction.label}"?`}
          description="This permanently deletes the metric."
          confirmLabel="Remove"
          danger
          onConfirm={() => handleDeleteMetric(confirmAction.id)}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction?.type === 'deleteOffering' && (
        <ConfirmDialog
          title={`Remove "${confirmAction.label}"?`}
          description="This permanently deletes the offering."
          confirmLabel="Remove"
          danger
          onConfirm={() => handleDeleteOffering(confirmAction.id)}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
