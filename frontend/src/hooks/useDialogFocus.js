import { useEffect } from 'react'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Dialog keyboard contract shared by the cookie manager and newsletter popup:
// focus moves into the dialog when it opens, Tab/Shift+Tab stay inside it,
// Escape calls onClose (when given), and focus returns to whatever had it
// before the dialog opened.
export default function useDialogFocus(ref, open, onClose, initialSelector) {
  useEffect(() => {
    if (!open || !ref.current) return undefined
    const previous = document.activeElement
    const node = ref.current
    const items = () => [...node.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null || el === document.activeElement)
    const first = (initialSelector && node.querySelector(initialSelector)) || items()[0]
    first?.focus()
    function onKey(e) {
      if (e.key === 'Escape' && onClose) {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const list = items()
      if (!list.length) return
      const firstEl = list[0]
      const lastEl = list[list.length - 1]
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault()
        lastEl.focus()
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault()
        firstEl.focus()
      }
    }
    node.addEventListener('keydown', onKey)
    return () => {
      node.removeEventListener('keydown', onKey)
      if (previous && typeof previous.focus === 'function' && document.contains(previous)) previous.focus()
    }
  }, [ref, open, onClose, initialSelector])
}
