import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Bookmark, BookmarkCheck } from 'lucide-react'
import { toast } from 'react-toastify'
import { saveItem, unsaveItem, checkSaved } from '../../api/saved'

const DEFAULT_CLASS =
  'inline-flex shrink-0 items-center gap-2 self-start border px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy-500 disabled:cursor-not-allowed disabled:opacity-60'

// Reusable save/bookmark toggle for the six public detail pages (Article,
// Job, Opportunity, Resource, Event, Learning Program) — backed by
// backend app/api/v1/saved.py. Always a plain sibling control, never
// nested inside an existing <Link> — see AccountSavedPage, which relies
// on exactly that to drop this next to cards whose entire body is a link.
export default function SaveButton({ contentType, contentId, className }) {
  const navigate = useNavigate()
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [saved, setSaved] = useState(false)
  const [ready, setReady] = useState(false)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    let cancelled = false
    setReady(false)
    if (!accessToken || !contentType || !contentId) {
      setReady(true)
      return undefined
    }
    checkSaved(contentType, contentId).then((isSaved) => {
      if (cancelled) return
      setSaved(isSaved)
      setReady(true)
    })
    return () => {
      cancelled = true
    }
  }, [accessToken, contentType, contentId])

  if (!accessToken) {
    return (
      <button
        type="button"
        onClick={() => navigate('/login')}
        className={className || `${DEFAULT_CLASS} border-taupe-300 text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600`}
        aria-label="Sign in to save this for later"
      >
        <Bookmark size={16} /> Sign in to save
      </button>
    )
  }

  async function handleClick() {
    if (pending || !ready) return
    const nextSaved = !saved
    setPending(true)
    setSaved(nextSaved)
    try {
      if (nextSaved) {
        await saveItem(contentType, contentId)
      } else {
        await unsaveItem(contentType, contentId)
      }
    } catch {
      setSaved(!nextSaved)
      toast.error('Something went wrong. Please try again.')
    } finally {
      setPending(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending || !ready}
      aria-pressed={saved}
      aria-label={saved ? 'Remove from saved items' : 'Save for later'}
      className={
        className ||
        `${DEFAULT_CLASS} ${saved ? 'border-burgundy-500 text-burgundy-600' : 'border-taupe-300 text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600'}`
      }
    >
      {saved ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
      {saved ? 'Saved' : 'Save'}
    </button>
  )
}
