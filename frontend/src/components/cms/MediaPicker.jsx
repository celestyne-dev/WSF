import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-toastify'
import { X, Upload, Search, ImageOff, Check } from 'lucide-react'
import { fetchMediaLibrary, uploadMedia } from '../../api/media'
import MediaImage from '../ui/MediaImage'
import EmptyState from '../ui/EmptyState'

/**
 * Reusable media selector for every CMS screen that attaches an image —
 * article hero/body, person/author photos, org/sponsor logos, event/
 * resource covers, homepage modules, OG images. Renders a thumbnail +
 * "Choose image" trigger; the picker itself is a modal with search,
 * browse, and drag/drop upload, so no editor screen has to build its own
 * upload UI or know a media ID by hand.
 *
 * `value` — { id, mediaPath, altText, caption, credit } | null
 * `onChange(media | null)`
 */
export default function MediaPicker({ value, onChange, label = 'Image', aspect = 4 / 3 }) {
  const [open, setOpen] = useState(false)

  return (
    <div>
      {label && <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</p>}
      <div className="mt-1.5 flex items-center gap-3">
        <div className="flex h-20 w-28 shrink-0 items-center justify-center overflow-hidden border border-taupe-300 bg-taupe-100">
          {value?.mediaPath ? (
            <MediaImage media={value} variant="thumbnail" width={280} height={200} aspect={aspect} className="h-full w-full object-cover" />
          ) : (
            <ImageOff size={20} className="text-charcoal-600/40" />
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <button type="button" onClick={() => setOpen(true)} className="btn-secondary !px-3 !py-1.5 text-xs">
            {value ? 'Change image' : 'Choose image'}
          </button>
          {value && (
            <button type="button" onClick={() => onChange(null)} className="text-left text-xs text-charcoal-600/70 hover:text-burgundy-600">
              Remove
            </button>
          )}
        </div>
      </div>
      {open && (
        <MediaPickerModal
          onClose={() => setOpen(false)}
          onSelect={(media) => {
            onChange(media)
            setOpen(false)
          }}
        />
      )}
    </div>
  )
}

export function MediaPickerModal({ onClose, onSelect }) {
  const [tab, setTab] = useState('library')
  const [query, setQuery] = useState('')
  const [items, setItems] = useState(undefined)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [pendingFile, setPendingFile] = useState(null)
  const [pendingMeta, setPendingMeta] = useState({ altText: '', caption: '', credit: '' })
  const fileInputRef = useRef(null)

  useEffect(() => {
    let active = true
    setItems(undefined)
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

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  function stageFile(file) {
    if (!file) return
    setPendingFile(file)
    setPendingMeta({ altText: '', caption: '', credit: '' })
  }

  function handleDrop(e) {
    e.preventDefault()
    stageFile(e.dataTransfer.files?.[0])
  }

  async function confirmUpload() {
    if (!pendingFile) return
    setUploading(true)
    try {
      const media = await uploadMedia(pendingFile, pendingMeta)
      toast.success('Image uploaded.')
      onSelect(media)
    } catch (err) {
      toast.error(err.apiError?.message || 'Something went wrong uploading this file. Please try again.')
    } finally {
      setUploading(false)
      setPendingFile(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/70 p-4" role="dialog" aria-modal="true" aria-label="Media library">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col bg-ivory shadow-card">
        <div className="flex items-center justify-between border-b border-taupe-200 px-5 py-4">
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => setTab('library')}
              className={`text-sm font-semibold ${tab === 'library' ? 'text-charcoal' : 'text-charcoal-600/60'}`}
            >
              Media Library
            </button>
            <button
              type="button"
              onClick={() => setTab('upload')}
              className={`text-sm font-semibold ${tab === 'upload' ? 'text-charcoal' : 'text-charcoal-600/60'}`}
            >
              Upload
            </button>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 text-charcoal-600 hover:text-charcoal">
            <X size={20} />
          </button>
        </div>

        {tab === 'library' && (
          <>
            <div className="border-b border-taupe-200 px-5 py-3">
              <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
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
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {error && <EmptyState title="Couldn't load the media library" description={error} />}
              {!error && items === undefined && <p className="py-12 text-center text-sm text-charcoal-600">Loading…</p>}
              {!error && items && items.length === 0 && <EmptyState title="No media found" description="Try a different search, or upload a new image." />}
              {!error && items && items.length > 0 && (
                <>
                  <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
                    {items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => onSelect(item)}
                        className="group relative overflow-hidden border border-taupe-200 bg-white text-left focus:outline-none focus:ring-2 focus:ring-burgundy-500"
                      >
                        <MediaImage media={item} variant="thumbnail" width={280} height={210} aspect={4 / 3} className="aspect-[4/3] w-full object-cover" />
                        <div className="absolute inset-0 hidden items-center justify-center bg-charcoal/50 group-hover:flex">
                          <Check size={20} className="text-ivory" />
                        </div>
                        <p className="truncate px-2 py-1.5 text-[11px] text-charcoal-600">{item.originalFilename || item.altText || `Media #${item.id}`}</p>
                      </button>
                    ))}
                  </div>
                  {pagination?.page < pagination?.totalPages && (
                    <button type="button" onClick={() => setPage((p) => p + 1)} className="btn-secondary mt-4 w-full !py-2 text-xs">
                      Load more
                    </button>
                  )}
                </>
              )}
            </div>
          </>
        )}

        {tab === 'upload' && (
          <div className="flex-1 overflow-y-auto p-5">
            {!pendingFile && (
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className="flex cursor-pointer flex-col items-center justify-center gap-2 border-2 border-dashed border-taupe-300 px-6 py-16 text-center hover:border-burgundy-400"
              >
                <Upload size={24} className="text-charcoal-600/60" />
                <p className="text-sm font-medium text-charcoal">Drag and drop an image, or click to browse</p>
                <p className="text-xs text-charcoal-600/60">JPG, PNG, or WebP. Converted to responsive WebP variants automatically.</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => stageFile(e.target.files?.[0])}
                />
              </div>
            )}
            {pendingFile && (
              <div className="space-y-3">
                <p className="text-sm font-medium text-charcoal">{pendingFile.name}</p>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                    Alt text <span className="normal-case text-charcoal-600/60">— for accessibility and SEO</span>
                  </label>
                  <input
                    autoFocus
                    value={pendingMeta.altText}
                    onChange={(e) => setPendingMeta((m) => ({ ...m, altText: e.target.value }))}
                    className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Caption</label>
                    <input
                      value={pendingMeta.caption}
                      onChange={(e) => setPendingMeta((m) => ({ ...m, caption: e.target.value }))}
                      className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Credit</label>
                    <input
                      value={pendingMeta.credit}
                      onChange={(e) => setPendingMeta((m) => ({ ...m, credit: e.target.value }))}
                      className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <button type="button" onClick={() => setPendingFile(null)} disabled={uploading} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
                    Choose a different file
                  </button>
                  <button type="button" onClick={confirmUpload} disabled={uploading} className="btn-primary !px-4 !py-2 text-xs disabled:opacity-60">
                    {uploading ? 'Uploading…' : 'Upload'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
