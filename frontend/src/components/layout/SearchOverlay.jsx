import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { X, Search } from 'lucide-react'
import { toggleSearch } from '../../features/navigation/uiSlice'

export default function SearchOverlay() {
  const open = useSelector((s) => s.ui.searchOpen)
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') dispatch(toggleSearch(false))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dispatch])

  if (!open) return null

  function handleSubmit(e) {
    e.preventDefault()
    if (!query.trim()) return
    navigate(`/search?q=${encodeURIComponent(query.trim())}`)
    dispatch(toggleSearch(false))
    setQuery('')
  }

  return (
    <div className="fixed inset-0 z-50 bg-charcoal/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Site search">
      <div className="mx-auto mt-24 w-full max-w-2xl px-4">
        <div className="bg-ivory p-6 shadow-card sm:p-8">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Search Women Shaping Futures</p>
            <button
              type="button"
              onClick={() => dispatch(toggleSearch(false))}
              aria-label="Close search"
              className="p-1 text-charcoal-600 hover:text-charcoal"
            >
              <X size={22} />
            </button>
          </div>
          <form onSubmit={handleSubmit} className="mt-4 flex items-center gap-3 border-b-2 border-charcoal pb-3">
            <Search size={22} className="shrink-0 text-charcoal-600" />
            <input
              ref={inputRef}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search stories, people, jobs, opportunities…"
              className="w-full bg-transparent font-serif text-xl text-charcoal placeholder:text-charcoal-600/50 focus:outline-none"
            />
          </form>
          <p className="mt-4 text-xs text-charcoal-600">Press Enter to search, or Esc to close.</p>
        </div>
      </div>
    </div>
  )
}
