import { useState } from 'react'
import { ChevronLeft, ChevronRight, Plus, X, Star } from 'lucide-react'
import { MediaPickerModal } from './MediaPicker'
import MediaImage from '../ui/MediaImage'

/**
 * Ordered supplementary gallery for a Product, on top of its single
 * primary/cover image (set separately via MediaPicker). Reuses the same
 * library/upload modal as MediaPicker so there's one place that knows how
 * to browse or upload media. `value` is an array of { media } entries (the
 * shape ProductImageSchema dumps); `onChange` replaces the whole ordered
 * array, which the editor persists to the backend on save — not just kept
 * in local React state.
 */
export default function GalleryEditor({ value = [], onChange, label = 'Gallery images' }) {
  const [open, setOpen] = useState(false)

  function addMedia(media) {
    onChange([...value, { media }])
    setOpen(false)
  }

  function removeAt(index) {
    onChange(value.filter((_, i) => i !== index))
  }

  function moveTo(index, direction) {
    const target = index + direction
    if (target < 0 || target >= value.length) return
    const next = [...value]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return (
    <div>
      {label && <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</p>}
      <p className="mt-0.5 text-xs text-charcoal-600/70">
        Additional images shown in the product gallery, beyond the primary image above. The first image sets the order shown on the product page.
      </p>
      <div className="mt-2 flex flex-wrap gap-3">
        {value.map((item, index) => (
          <div key={item.media?.id ?? index} className="group relative h-24 w-24 shrink-0 overflow-hidden border border-taupe-300 bg-taupe-100">
            {item.media?.mediaPath ? (
              <MediaImage media={item.media} variant="thumbnail" width={200} height={200} aspect={1} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-charcoal-600/40">—</div>
            )}
            <div className="absolute inset-0 hidden items-center justify-between bg-charcoal/60 px-1 group-hover:flex">
              <button type="button" onClick={() => moveTo(index, -1)} aria-label="Move earlier" disabled={index === 0} className="p-1 text-ivory disabled:opacity-30">
                <ChevronLeft size={14} />
              </button>
              <button type="button" onClick={() => removeAt(index)} aria-label="Remove image" className="p-1 text-ivory hover:text-rose-300">
                <X size={14} />
              </button>
              <button type="button" onClick={() => moveTo(index, 1)} aria-label="Move later" disabled={index === value.length - 1} className="p-1 text-ivory disabled:opacity-30">
                <ChevronRight size={14} />
              </button>
            </div>
            {index === 0 && (
              <span className="absolute left-1 top-1 flex items-center gap-0.5 bg-charcoal/70 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-ivory">
                <Star size={9} /> First
              </span>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex h-24 w-24 shrink-0 flex-col items-center justify-center gap-1 border border-dashed border-taupe-300 text-charcoal-600/60 hover:border-burgundy-400 hover:text-burgundy-600"
        >
          <Plus size={18} />
          <span className="text-[10px] font-medium">Add image</span>
        </button>
      </div>
      {open && <MediaPickerModal onClose={() => setOpen(false)} onSelect={addMedia} />}
    </div>
  )
}
