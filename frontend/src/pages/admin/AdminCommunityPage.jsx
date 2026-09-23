import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { Save, Eye, EyeOff, Plus, X } from 'lucide-react'
import { fetchCommunityPage, updateCommunityPage, updateCommunityPageStatus } from '../../api/community'
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

export default function AdminCommunityPage() {
  const [page, setPage] = useState(null)
  const [form, setForm] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)

  useEffect(() => {
    let active = true
    fetchCommunityPage()
      .then((res) => {
        if (!active) return
        setPage(res)
        setForm(res)
      })
      .catch(() => active && setLoadError('Something went wrong loading the Community page. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await updateCommunityPage(form)
      setPage(updated)
      setForm(updated)
      toast.success('Community page updated.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong saving the page.')
    } finally {
      setSaving(false)
    }
  }

  async function applyStatus(status) {
    try {
      const updated = await updateCommunityPageStatus(status)
      setPage(updated)
      setForm(updated)
      toast.success(status === 'published' ? 'Community page is now live.' : 'Community page unpublished.')
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating status.')
    } finally {
      setConfirmAction(null)
    }
  }

  function handleAddBenefit() {
    setForm({ ...form, benefits: [...form.benefits, { title: '', description: '' }] })
  }
  function handleBenefitChange(index, key, value) {
    setForm({ ...form, benefits: form.benefits.map((b, i) => (i === index ? { ...b, [key]: value } : b)) })
  }
  function handleRemoveBenefit(index) {
    setForm({ ...form, benefits: form.benefits.filter((_, i) => i !== index) })
  }

  function handleAddFaq() {
    setForm({ ...form, faq: [...form.faq, { question: '', answer: '' }] })
  }
  function handleFaqChange(index, key, value) {
    setForm({ ...form, faq: form.faq.map((f, i) => (i === index ? { ...f, [key]: value } : f)) })
  }
  function handleRemoveFaq(index) {
    setForm({ ...form, faq: form.faq.filter((_, i) => i !== index) })
  }

  if (loadError) return <EmptyState title="Couldn't load the Community page" description={loadError} />
  if (form === null) return <PageLoader />

  return (
    <div>
      <AdminPageHeader
        title="Community Page"
        description="Manages the public /community page — hero, intro, benefits, and how to join. Members are managed separately."
        actions={page && <StatusBadge status={page.status} />}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-6">
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

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Introduction</p>
            <ArticleBlockEditor blocks={form.introContent} onChange={(introContent) => setForm({ ...form, introContent })} />
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Benefits</p>
              <button type="button" onClick={handleAddBenefit} className="btn-secondary !px-3 !py-1.5 text-xs">
                <Plus size={14} /> Add benefit
              </button>
            </div>
            <p className="mt-1 text-xs text-charcoal-600/60">Only list benefits WSF can currently deliver.</p>
            <div className="mt-3 space-y-3">
              {form.benefits.length === 0 && <p className="text-sm text-charcoal-600/60">No benefits listed yet.</p>}
              {form.benefits.map((b, index) => (
                <div key={index} className="border border-taupe-200 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 space-y-2">
                      <input value={b.title} onChange={(e) => handleBenefitChange(index, 'title', e.target.value)} placeholder="Benefit title" className={inputClass} />
                      <textarea rows={2} value={b.description} onChange={(e) => handleBenefitChange(index, 'description', e.target.value)} placeholder="Description" className={inputClass} />
                    </div>
                    <button type="button" onClick={() => handleRemoveBenefit(index)} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Remove benefit">
                      <X size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Who it's for &amp; how to join</p>
            <div className="space-y-4">
              <Field label="Who it's for">
                <textarea rows={2} value={form.whoForText} onChange={(e) => setForm({ ...form, whoForText: e.target.value })} className={inputClass} />
              </Field>
              <Field label="How to join">
                <textarea rows={2} value={form.howToJoinText} onChange={(e) => setForm({ ...form, howToJoinText: e.target.value })} className={inputClass} />
              </Field>
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Call to action</p>
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
          </div>

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
                      <input value={entry.question} onChange={(e) => handleFaqChange(index, 'question', e.target.value)} placeholder="Question" className={inputClass} />
                      <textarea rows={2} value={entry.answer} onChange={(e) => handleFaqChange(index, 'answer', e.target.value)} placeholder="Answer" className={inputClass} />
                    </div>
                    <button type="button" onClick={() => handleRemoveFaq(index)} className="text-charcoal-600/60 hover:text-rose-600" aria-label="Remove question">
                      <X size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">SEO</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Title" hint="optional">
                <input value={form.seo?.title || ''} onChange={(e) => setForm({ ...form, seo: { ...form.seo, title: e.target.value } })} className={inputClass} />
              </Field>
              <Field label="Robots" hint="optional">
                <input value={form.seo?.robots || ''} onChange={(e) => setForm({ ...form, seo: { ...form.seo, robots: e.target.value } })} className={inputClass} />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Meta description" hint="optional">
                <textarea rows={2} value={form.seo?.description || ''} onChange={(e) => setForm({ ...form, seo: { ...form.seo, description: e.target.value } })} className={inputClass} />
              </Field>
            </div>
            <p className="mt-2 text-xs text-charcoal-600/60">Canonical URL is fixed at /community.</p>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-5 !py-2.5 text-xs disabled:opacity-60">
              <Save size={13} /> {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>

        <div className="space-y-4">
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
        </div>
      </div>

      {confirmAction?.type === 'publish' && (
        <ConfirmDialog
          title="Publish the Community page?"
          description="The page becomes visible at /community immediately."
          confirmLabel="Publish"
          onConfirm={() => applyStatus('published')}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction?.type === 'unpublish' && (
        <ConfirmDialog
          title="Unpublish the Community page?"
          description="The public /community page will stop rendering until republished."
          confirmLabel="Unpublish"
          danger
          onConfirm={() => applyStatus('draft')}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
