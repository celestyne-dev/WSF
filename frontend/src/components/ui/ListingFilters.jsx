import { useId, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'

// Filter area for listing pages: always open from lg up; below lg it is a
// compact toggle (with an active-filter count) so phones are not faced with
// every select at once.
export default function ListingFilters({ activeCount = 0, children, search }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  return (
    <div className="border-b border-taupe-200 pb-6">
      <div className="flex flex-wrap items-center gap-3">
        {search}
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
          className="rounded-control inline-flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2 text-sm font-semibold text-charcoal lg:hidden"
        >
          <SlidersHorizontal size={15} aria-hidden="true" /> Filters{activeCount > 0 ? ` (${activeCount})` : ''}
        </button>
      </div>
      <div id={panelId} className={`${open ? 'flex' : 'hidden'} mt-4 flex-wrap items-end gap-4 lg:flex`}>
        {children}
      </div>
    </div>
  )
}
