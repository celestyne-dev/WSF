import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Save, Eye, Archive, Send, CheckCircle2, Download } from 'lucide-react'
import {
  fetchNewsletterIssueBySlug,
  createNewsletterIssue,
  updateNewsletterIssue,
  recordExternalSend,
  fetchSendRecords,
  exportIssueRecipients,
  archiveNewsletterIssue,
  estimateAudience,
} from '../../api/newsletter'
import { ISSUE_STATUS_LABELS } from '../../constants/newsletter'
import { fetchArticles } from '../../api/articles'
import { fetchTopics } from '../../api/taxonomies'
import { RESERVED_SLUGS } from '../../constants/routes'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import MediaPicker from '../../components/cms/MediaPicker'
import ArticleBlockEditor from '../../components/cms/ArticleBlockEditor'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const NEWSLETTER_BLOCK_TYPES = [
  'paragraph', 'heading', 'list', 'blockquote', 'pullquote', 'image', 'highlight', 'divider',
  'button', 'articleCard', 'footerNote',
]

function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

const STATUSES = ['draft', 'ready', 'archived']

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

function blankForm() {
  return {
    title: '',
    slug: '',
    subject: '',
    preheader: '',
    content: [],
    coverMedia: null,
    summary: '',
    featuredArticleSlug: '',
    featuredArticleTitle: '',
    status: 'draft',
    topicSlugs: [],
    countryCodesText: '',
    scheduledAt: '',
    sendTimezone: 'UTC',
  }
}

function toForm(issue) {
  return {
    title: issue.title || '',
    slug: issue.slug || '',
    subject: issue.subject || '',
    preheader: issue.preheader || '',
    content: issue.content || [],
    coverMedia: issue.coverMedia || null,
    summary: issue.summary || '',
    featuredArticleSlug: issue.featuredArticleSlug || '',
    featuredArticleTitle: issue.featuredArticle?.title || '',
    status: issue.status === 'sent' ? 'archived' : issue.status || 'draft',
    topicSlugs: issue.audienceFilter?.topicSlugs || [],
    countryCodesText: (issue.audienceFilter?.countryCodes || []).join(', '),
    scheduledAt: issue.scheduledAt ? issue.scheduledAt.slice(0, 16) : '',
    sendTimezone: issue.sendTimezone || 'UTC',
  }
}

function buildAudienceFilter(form) {
  const countryCodes = form.countryCodesText
    .split(',')
    .map((c) => c.trim().toUpperCase())
    .filter(Boolean)
  if (form.topicSlugs.length === 0 && countryCodes.length === 0) return null
  return { topicSlugs: form.topicSlugs, countryCodes }
}

export default function AdminNewsletterEditor() {
  const { slug: slugParam } = useParams()
  const navigate = useNavigate()
  const isNew = !slugParam || slugParam === 'new'

  const [issue, setIssue] = useState(null)
  const [topics, setTopics] = useState([])
  const [articleSearch, setArticleSearch] = useState('')
  const [articleResults, setArticleResults] = useState([])
  const [form, setForm] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [slugTouched, setSlugTouched] = useState(!isNew)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [estimatedRecipients, setEstimatedRecipients] = useState(null)
  const [confirmAction, setConfirmAction] = useState(null)
  const [sendRecords, setSendRecords] = useState([])
  const [sendForm, setSendForm] = useState({ providerName: '', externalReference: '', recipientCount: '', sentAt: '' })

  useEffect(() => {
    let active = true
    Promise.all([
      fetchTopics(),
      isNew ? Promise.resolve(null) : fetchNewsletterIssueBySlug(slugParam),
      isNew ? Promise.resolve([]) : fetchSendRecords(slugParam).catch(() => []),
    ])
      .then(([topicList, existing, records]) => {
        if (!active) return
        setTopics(topicList)
        setSendRecords(records)
        if (isNew) {
          setForm(blankForm())
        } else if (existing) {
          setIssue(existing)
          setForm(toForm(existing))
        } else {
          setNotFound(true)
        }
      })
      .catch(() => active && setLoadError('Something went wrong loading the newsletter editor. Please try again.'))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slugParam, isNew])

  useEffect(() => {
    if (!form) return
    let active = true
    const audienceFilter = buildAudienceFilter(form)
    estimateAudience(audienceFilter)
      .then((count) => active && setEstimatedRecipients(count))
      .catch(() => {})
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form?.topicSlugs, form?.countryCodesText])

  useEffect(() => {
    if (!articleSearch) {
      setArticleResults([])
      return
    }
    let active = true
    fetchArticles({ query: articleSearch, pageSize: 8 }).then((res) => active && setArticleResults(res.items)).catch(() => {})
    return () => {
      active = false
    }
  }, [articleSearch])

  function updateField(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'title' && !slugTouched) {
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
    if (RESERVED_SLUGS.includes(slug)) return `"${slug}" is a reserved system route and cannot be used as a newsletter slug.`
    return null
  }

  async function handleSave(nextStatus) {
    const slugError = validateSlug(form.slug)
    if (slugError) {
      setErrors({ slug: slugError })
      toast.error(slugError)
      return
    }
    if (!form.title) {
      toast.error('Add an internal title.')
      return
    }
    if (!form.subject) {
      toast.error('Add a subject line.')
      return
    }
    if (nextStatus === 'ready' && form.content.length === 0) {
      toast.error('Add content before marking this issue ready.')
      return
    }
    setErrors({})
    setSaving(true)

    const payload = {
      title: form.title,
      slug: form.slug,
      subject: form.subject,
      preheader: form.preheader || null,
      content: form.content,
      coverMedia: form.coverMedia,
      summary: form.summary || null,
      featuredArticleSlug: form.featuredArticleSlug || null,
      status: nextStatus,
      audienceFilter: buildAudienceFilter(form),
      scheduledAt: form.scheduledAt ? new Date(form.scheduledAt).toISOString() : null,
      sendTimezone: form.sendTimezone || 'UTC',
    }

    try {
      const saved = isNew ? await createNewsletterIssue(payload) : await updateNewsletterIssue(slugParam, payload)
      toast.success(`Issue saved: ${ISSUE_STATUS_LABELS[nextStatus] || nextStatus}.`)
      if (isNew) navigate(`/admin/newsletter/issues/${saved.slug}`)
      else {
        setIssue(saved)
        setForm(toForm(saved))
      }
    } catch (err) {
      const message = err?.response?.data?.error?.message || 'Something went wrong saving this issue. Please try again.'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function loadRecords() {
    if (isNew) return
    try {
      setSendRecords(await fetchSendRecords(slugParam))
    } catch {
      setSendRecords([])
    }
  }

  async function handleExport() {
    try {
      await exportIssueRecipients(slugParam)
      toast.success('Recipient CSV downloaded (confirmed subscribers only). The export is recorded.')
      loadRecords()
    } catch (err) {
      toast.error(err?.response?.status === 403 ? "You don't have permission to export recipients." : 'The export failed.')
    }
  }

  async function handleRecordSend(e) {
    e.preventDefault()
    try {
      const updated = await recordExternalSend(slugParam, sendForm)
      setIssue(updated)
      setForm(toForm(updated))
      toast.success('External send recorded. WSF did not send this email itself.')
      loadRecords()
    } catch (err) {
      toast.error(err?.apiError?.message || err?.response?.data?.error?.message || 'Something went wrong.')
    }
  }

  async function handleArchive() {
    try {
      const updated = await archiveNewsletterIssue(slugParam)
      setIssue(updated)
      setForm(toForm(updated))
      toast.success('Issue archived.')
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong.')
    } finally {
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load the newsletter editor" description={loadError} />
  if (notFound) return <EmptyState title="Newsletter issue not found" description="This issue may have been removed or the URL is incorrect." />
  if (form === undefined) return <PageLoader />

  const actualStatus = issue?.status || 'draft'

  return (
    <div>
      <AdminPageHeader
        title={isNew ? 'New Newsletter Issue' : `Edit: ${form.title || 'Untitled'}`}
        description={isNew ? undefined : `Public archive URL (once sent): womenshapingfutures.org/newsletter/${form.slug}`}
        actions={
          <>
            <StatusBadge status={actualStatus} />
            {!isNew && actualStatus === 'sent' && (
              <a href={`/newsletter/${form.slug}`} target="_blank" rel="noreferrer" className="btn-secondary !px-4 !py-2 text-xs">
                <Eye size={14} /> View in archive
              </a>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Section title="Basic information">
            <Field label="Internal title" hint="how you'll find this draft — not shown to subscribers">
              <input value={form.title} onChange={(e) => updateField('title', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Slug" hint="used for the public archive URL, once sent">
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
            <Field label="Internal summary" hint="optional — a short note for your own reference, also shown as the archive teaser">
              <textarea rows={2} value={form.summary} onChange={(e) => updateField('summary', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Subject / preheader">
            <Field label="Subject line" hint="what subscribers see in their inbox">
              <input value={form.subject} onChange={(e) => updateField('subject', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <Field label="Preheader" hint="preview text shown next to the subject line">
              <input value={form.preheader} onChange={(e) => updateField('preheader', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
          </Section>

          <Section title="Content" description="Email-friendly blocks only — no columns or embeds. Use an Article card to link to a story, or a Button for any other call to action.">
            <ArticleBlockEditor blocks={form.content} onChange={(content) => updateField('content', content)} blockTypes={NEWSLETTER_BLOCK_TYPES} />
          </Section>

          <Section title="Featured article" description="Optional — shown at the top of the issue and on the archive listing.">
            {form.featuredArticleSlug ? (
              <div className="flex items-center justify-between border border-taupe-200 bg-taupe-50 px-3 py-2 text-sm">
                <div>
                  <p className="font-medium text-charcoal">{form.featuredArticleTitle}</p>
                  <p className="text-xs text-charcoal-600/70">/{form.featuredArticleSlug}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setForm((prev) => ({ ...prev, featuredArticleSlug: '', featuredArticleTitle: '' }))}
                  className="text-xs font-semibold text-charcoal-600/70 hover:text-rose-600"
                >
                  Remove
                </button>
              </div>
            ) : (
              <>
                <input value={articleSearch} onChange={(e) => setArticleSearch(e.target.value)} placeholder="Search published articles…" className="w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
                {articleResults.length > 0 && (
                  <div className="mt-1.5 max-h-40 divide-y divide-taupe-200 overflow-y-auto border border-taupe-200">
                    {articleResults.map((a) => (
                      <button
                        key={a.slug}
                        type="button"
                        onClick={() => {
                          setForm((prev) => ({ ...prev, featuredArticleSlug: a.slug, featuredArticleTitle: a.title }))
                          setArticleSearch('')
                          setArticleResults([])
                        }}
                        className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100"
                      >
                        {a.title}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </Section>

          <Section title="Media">
            <MediaPicker label="Cover image" aspect={1.91 / 1} value={form.coverMedia} onChange={(media) => updateField('coverMedia', media)} />
          </Section>

          <Section title="Audience / segment" description="Leave everything unselected to send to all active subscribers.">
            <Field label="Topics" hint="only subscribers interested in at least one selected topic">
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
              </div>
            </Field>
            <Field label="Countries" hint="optional — comma-separated ISO codes, e.g. US, GB, KE">
              <input value={form.countryCodesText} onChange={(e) => updateField('countryCodesText', e.target.value)} className="w-full max-w-sm border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
            </Field>
            <p className="text-sm text-charcoal-600">
              Estimated recipients: <span className="font-semibold text-charcoal">{estimatedRecipients ?? '—'}</span>{' '}
              <span className="text-xs text-charcoal-600/60">(informational only — not a delivery count)</span>
            </p>
          </Section>

          <Section title="Planned send date" description="Informational only: WSF never sends newsletters automatically.">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Planned date/time">
                <input type="datetime-local" value={form.scheduledAt} onChange={(e) => updateField('scheduledAt', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
              <Field label="Timezone" hint="e.g. UTC, America/New_York">
                <input value={form.sendTimezone} onChange={(e) => updateField('sendTimezone', e.target.value)} className="w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none" />
              </Field>
            </div>
          </Section>

          <Section title="Delivery" description="WSF prepares the issue and the recipient list; you send it through an external service and record it here. WSF does not transmit newsletters itself.">
            {!isNew && (
              <div className="space-y-4">
                <button type="button" onClick={handleExport} className="btn-secondary !px-4 !py-2 text-xs">
                  <Download size={13} /> Export recipients (confirmed subscribers, CSV)
                </button>
                {actualStatus !== 'sent' && actualStatus !== 'archived' && (
                  <form onSubmit={handleRecordSend} className="space-y-3 border border-taupe-200 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Record external send</p>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <label className="text-xs text-charcoal-600">Sending service
                        <input required maxLength={100} value={sendForm.providerName} onChange={(e) => setSendForm({ ...sendForm, providerName: e.target.value })} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
                      </label>
                      <label className="text-xs text-charcoal-600">Campaign / reference ID (optional)
                        <input maxLength={200} value={sendForm.externalReference} onChange={(e) => setSendForm({ ...sendForm, externalReference: e.target.value })} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
                      </label>
                      <label className="text-xs text-charcoal-600">Recipients
                        <input required type="number" min="0" value={sendForm.recipientCount} onChange={(e) => setSendForm({ ...sendForm, recipientCount: e.target.value })} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
                      </label>
                      <label className="text-xs text-charcoal-600">Sent at (optional, defaults to now)
                        <input type="datetime-local" value={sendForm.sentAt} onChange={(e) => setSendForm({ ...sendForm, sentAt: e.target.value })} className="mt-1 w-full border border-taupe-300 px-3 py-2 text-sm" />
                      </label>
                    </div>
                    <button type="submit" className="btn-primary !px-4 !py-2 text-xs"><Send size={13} /> Record external send</button>
                  </form>
                )}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">History</p>
                  {sendRecords.length ? (
                    <ul className="mt-2 space-y-1 text-sm">
                      {sendRecords.map((r) => (
                        <li key={r.id}>
                          {r.kind === 'export' ? 'Recipient export' : `Sent externally via ${r.providerName}`}
                          {' · '}{r.recipientCount} recipients · {formatDate(r.occurredAt)}
                          {r.externalReference ? ` · ref ${r.externalReference}` : ''}{r.recordedBy ? ` · ${r.recordedBy}` : ''}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="mt-1 text-sm text-charcoal-600">No exports or sends recorded yet.</p>}
                </div>
              </div>
            )}
          </Section>
        </div>

        <div className="space-y-4">
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Publishing</p>
            <select value={form.status} onChange={(e) => updateField('status', e.target.value)} disabled={actualStatus === 'sent'} className="mt-2 w-full border border-taupe-300 px-3 py-2 text-sm disabled:bg-taupe-100">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {ISSUE_STATUS_LABELS[s]}
                </option>
              ))}
            </select>

            <div className="mt-4 space-y-2">
              {actualStatus !== 'sent' && (
                <>
                  <button type="button" onClick={() => handleSave('draft')} disabled={saving} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
                    <Save size={13} /> {saving ? 'Saving…' : 'Save draft'}
                  </button>
                  <button type="button" onClick={() => handleSave('ready')} disabled={saving} className="btn-primary w-full !py-2 text-xs disabled:opacity-60">
                    <CheckCircle2 size={13} /> Save as ready to export
                  </button>
                </>
              )}
              {!isNew && actualStatus !== 'archived' && (
                <button type="button" onClick={() => setConfirmAction('archive')} className="btn-secondary w-full !py-2 text-xs">
                  <Archive size={13} /> Archive
                </button>
              )}
            </div>
          </div>

          <Link to="/admin/newsletter/issues" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all issues
          </Link>
        </div>
      </div>

      {confirmAction === 'archive' && (
        <ConfirmDialog
          title="Archive this issue?"
          description="It will be hidden from the public archive (if sent) and removed from active lists. The record is kept."
          confirmLabel="Archive"
          onConfirm={handleArchive}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
