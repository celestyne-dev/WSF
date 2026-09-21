import { useEffect } from 'react'

/**
 * Shared confirm-before-destructive-action dialog for the CMS — delete,
 * archive, unpublish, etc. Every admin screen that needs a confirmation
 * renders this instead of rolling its own, so the interaction (and its
 * Escape-to-cancel/backdrop behavior) stays consistent.
 */
export default function ConfirmDialog({ title, description, confirmLabel = 'Confirm', danger = true, onConfirm, onCancel }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/70 p-4" role="alertdialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-sm bg-ivory p-6 shadow-card">
        <h3 className="font-serif text-lg font-semibold text-charcoal">{title}</h3>
        {description && <p className="mt-2 text-sm text-charcoal-600">{description}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="btn-secondary !px-4 !py-2 text-xs">
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`!px-4 !py-2 text-xs font-semibold text-ivory ${danger ? 'bg-rose-600 hover:bg-rose-700' : 'bg-burgundy-500 hover:bg-burgundy-600'}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
