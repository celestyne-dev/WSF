import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-toastify'
import { Upload, Search, Trash2, X } from 'lucide-react'
import { fetchMediaLibrary, uploadMedia, updateMediaMetadata, deleteMedia } from '../../api/media'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import MediaImage from '../../components/ui/MediaImage'
import EmptyState from '../../components/ui/EmptyState'
import PageLoader from '../../components/ui/PageLoader'

function formatBytes(bytes) {
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

export default function AdminMediaLibrary() {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    let active = true
    setError(null)
    if (page === 1) setItems(undefined)
    fetchMediaLibrary({ q: query || undefined, page, pageSize: 24 })
      .then(({ items: rows, pagination: p }) => {
        if (!active) return
        setItems((prev) => (page === 1 ? rows : [...(prev || []), ...rows]))
        setPagination(p)
      })
      .catch(() => active && setError('Something went wrong loading the media library. Please try again.'))
    return () => {
      active = false
    }
  }, [query, page])

  function reload() {
    setPage(1)
    setItems(undefined)
    fetchMediaLibrary({ q: query || undefined, page: 1, pageSize: 24 })
      .then(({ items: rows, pagination: p }) => {
        setItems(rows)
        setPagination(p)
      })
      .catch(() => setError('Something went wrong loading the media library. Please try again.'))
  }

  async function handleUpload(file) {
    if (!file) return
    setUploading(true)
    try {
      const media = await uploadMedia(file, {})
      toast.success('Image uploaded.')
      reload()
      setSelected(media)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong uploading this file. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  async function handleDelete(id) {
    setConfirmDeleteId(null)
    const result = await deleteMedia(id)
    if (result.success) {
      toast.success('Image deleted.')
      setSelected(null)
      setItems((prev) => (prev || []).filter((m) => m.id !== id))
    } else {
      toast.error(result.reason)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Media Library"
        description="Every image uploaded to WSF, with alt text, captions, and credit managed in one place. Reused across articles, profiles, and CMS sections through the media picker."
        actions={
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
            <Upload size={14} /> {uploading ? 'Uploading…' : 'Upload image'}
          </button>
        }
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        disabled={uploading}
        onChange={(e) => handleUpload(e.target.files?.[0])}
      />

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="mb-5 flex items-center gap-2 border border-dashed border-taupe-300 bg-white px-4 py-3 text-xs text-charcoal-600"
      >
        <Upload size={14} className="shrink-0 text-charcoal-600/60" />
        Drag and drop an image anywhere in this box to upload it.
      </div>

      <div className="mb-5 flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2 sm:max-w-sm">
        <Search size={15} className="text-charcoal-600/60" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setPage(1)
          }}
          placeholder="Search by filename, alt text, caption, or credit…"
          className="w-full text-sm focus:outline-none"
        />
      </div>

      {error && <EmptyState title="Couldn't load the media library" description={error} />}
      {!error && items === undefined && <PageLoader />}
      {!error && items && items.length === 0 && <EmptyState title="No media uploaded yet" description="Upload an image to get started." />}
      {!error && items && items.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelected(item)}
                className="group overflow-hidden border border-taupe-200 bg-white text-left focus:outline-none focus:ring-2 focus:ring-burgundy-500"
              >
                <MediaImage mediaPath={item.mediaPath} alt={item.altText} width={400} height={300} aspect={4 / 3} className="aspect-[4/3] w-full object-cover" />
                <div className="p-2">
                  <p className="truncate text-xs font-medium text-charcoal">{item.originalFilename || `Media #${item.id}`}</p>
                  <p className="truncate text-xs text-charcoal-600/60">{item.altText || 'No alt text'}</p>
                </div>
              </button>
            ))}
          </div>
          {pagination?.page < pagination?.totalPages && (
            <button type="button" onClick={() => setPage((p) => p + 1)} className="btn-secondary mt-5 w-full !py-2 text-xs">
              Load more
            </button>
          )}
        </>
      )}

      {selected && (
        <MediaDetailPanel
          media={selected}
          onClose={() => setSelected(null)}
          onSaved={(updated) => {
            setSelected(updated)
            setItems((prev) => (prev || []).map((m) => (m.id === updated.id ? updated : m)))
          }}
          onDelete={() => setConfirmDeleteId(selected.id)}
        />
      )}

      {confirmDeleteId && (
        <ConfirmDialog
          title="Delete this image?"
          description="This can't be undone. If it's still attached to an article, profile, or other content, WSF will refuse the delete and tell you where it's used."
          confirmLabel="Delete"
          onConfirm={() => handleDelete(confirmDeleteId)}
          onCancel={() => setConfirmDeleteId(null)}
        />
      )}
    </div>
  )
}

function MediaDetailPanel({ media, onClose, onSaved, onDelete }) {
  const [form, setForm] = useState({ altText: media.altText, caption: media.caption, credit: media.credit, copyrightSource: media.copyrightSource })
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await updateMediaMetadata(media.id, form)
      toast.success('Metadata saved.')
      onSaved(updated)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong saving this metadata. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-charcoal/60" role="dialog" aria-modal="true" aria-label="Media details">
      <div className="flex h-full w-full max-w-md flex-col overflow-y-auto bg-ivory p-6 shadow-card">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Media details</p>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 text-charcoal-600 hover:text-charcoal">
            <X size={18} />
          </button>
        </div>

        <MediaImage mediaPath={media.mediaPath} alt={media.altText} width={640} height={480} aspect={4 / 3} className="mb-4 w-full border border-taupe-200 object-cover" />

        <dl className="mb-5 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-charcoal-600">
          <dt className="font-semibold">Filename</dt>
          <dd className="truncate">{media.originalFilename || '—'}</dd>
          <dt className="font-semibold">Type</dt>
          <dd>{media.mimeType || '—'}</dd>
          <dt className="font-semibold">Dimensions</dt>
          <dd>{media.width && media.height ? `${media.width} × ${media.height}` : '—'}</dd>
          <dt className="font-semibold">Size</dt>
          <dd>{formatBytes(media.fileSize)}</dd>
          <dt className="font-semibold">Uploaded by</dt>
          <dd>{media.uploadedBy || '—'}</dd>
          <dt className="font-semibold">Uploaded</dt>
          <dd>{media.createdAt ? formatDate(media.createdAt) : '—'}</dd>
        </dl>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Alt text <span className="normal-case text-charcoal-600/60">— required for accessibility and SEO</span></label>
            <input value={form.altText || ''} onChange={(e) => setForm((f) => ({ ...f, altText: e.target.value }))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Caption</label>
            <input value={form.caption || ''} onChange={(e) => setForm((f) => ({ ...f, caption: e.target.value }))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Credit</label>
            <input value={form.credit || ''} onChange={(e) => setForm((f) => ({ ...f, credit: e.target.value }))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Copyright / source</label>
            <input value={form.copyrightSource || ''} onChange={(e) => setForm((f) => ({ ...f, copyrightSource: e.target.value }))} className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none" />
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between gap-3">
          <button type="button" onClick={onDelete} className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700">
            <Trash2 size={14} /> Delete
          </button>
          <button type="button" onClick={handleSave} disabled={saving} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
