import { useEffect, useRef } from 'react'

// Modal confirmation/report dialog on the native <dialog> element:
// showModal() makes the rest of the page inert, traps Tab inside, closes on
// Escape and is announced as a dialog. Focus returns to the control that
// opened it.
export default function CommentDialog({ open, titleId, title, onClose, children }) {
  const ref = useRef(null)
  const opener = useRef(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      opener.current = document.activeElement
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return undefined
    const handleClose = () => {
      onClose?.()
      const target = opener.current
      if (target && typeof target.focus === 'function') target.focus()
    }
    dialog.addEventListener('close', handleClose)
    return () => dialog.removeEventListener('close', handleClose)
  }, [onClose])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      className="w-[min(92vw,460px)] rounded-card border border-taupe-200 bg-white p-6 text-charcoal shadow-xl backdrop:bg-charcoal/40"
    >
      <h3 id={titleId} className="font-serif text-xl font-semibold">{title}</h3>
      {open && <div className="mt-3">{children}</div>}
    </dialog>
  )
}
