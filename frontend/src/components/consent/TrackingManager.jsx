import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { consentSnapshot, onConsentChange } from '../../utils/consent'
import { createGa4 } from '../../utils/trackers/ga4'

// One instance per page load: a loaded tag can't be unloaded, only stopped.
const ga4 = typeof window !== 'undefined' ? createGa4() : null
let lastViewed = null

// One page_view per route; also sent when measurement starts on a page
// (settings arrived, or consent was just given), never twice for one path.
function viewCurrentPage() {
  if (!ga4?.active) return
  const path = window.location.pathname + window.location.search
  if (path === lastViewed) return
  lastViewed = path
  ga4.pageView(path, document.title)
}

// Connects optional third-party measurement to Studio settings (public
// settings `tracking`, only configured IDs are present) and to consent.
// Renders nothing. Every integration is inactive without its ID, and runs
// only while its consent category is granted (utils/consent.js).
export default function TrackingManager() {
  const tracking = useSelector((s) => s.site.settings?.tracking)
  const { pathname, search } = useLocation()
  const gaId = tracking?.ga4MeasurementId || null

  useEffect(() => {
    if (!ga4) return undefined
    ga4.configure(gaId)
    ga4.applyConsent(consentSnapshot().analytics)
    viewCurrentPage()
    return onConsentChange((snap) => {
      ga4.applyConsent(snap.analytics)
      if (!ga4.active) lastViewed = null
      viewCurrentPage()
    })
  }, [gaId])

  useEffect(() => {
    viewCurrentPage()
  }, [pathname, search])

  return null
}
