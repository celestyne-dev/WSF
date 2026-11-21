import { useState } from 'react'
import { firstPaintSnapshotFor } from '../../utils/firstPaintSnapshot'

// `asRoot`: rendered directly in #root (the app-level Suspense fallback),
// where the server's fixed header placeholder is still on screen, so the
// snapshot keeps its `data-wsf-prerender` main and the header-height reserve
// that goes with it. Inside a layout it is a plain block under React's header.
export default function PageLoader({ asRoot = false }) {
  const [snap] = useState(() =>
    typeof window === 'undefined' ? null : firstPaintSnapshotFor(`${window.location.pathname}${window.location.search}`),
  )
  if (snap) {
    return asRoot ? (
      <main data-wsf-prerender={snap.kind} data-wsf-first-paint-snapshot="" className={snap.className} dangerouslySetInnerHTML={{ __html: snap.html }} />
    ) : (
      <div data-wsf-first-paint-snapshot="" className={snap.className} dangerouslySetInnerHTML={{ __html: snap.html }} />
    )
  }
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="h-8 w-8 animate-spin border-2 border-taupe-300 border-t-burgundy-500" role="status" aria-label="Loading" />
    </div>
  )
}
