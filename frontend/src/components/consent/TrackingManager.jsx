import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { consentSnapshot, onConsentChange } from '../../utils/consent'
import { createGa4 } from '../../utils/trackers/ga4'
import { createLinkedInInsight, createMetaPixel, needsReload } from '../../utils/trackers/marketing'

// One instance each per page load: a loaded tag can't be unloaded, only
// stopped (GA4, Meta) or removed by reloading the page (LinkedIn).
const browser = typeof window !== 'undefined'
const ga4 = browser ? createGa4() : null
const linkedin = browser ? createLinkedInInsight() : null
const meta = browser ? createMetaPixel() : null
let lastViewed = null

// One page view per route; also sent when measurement starts on a page
// (settings arrived, or consent was just given), never twice for one path.
function viewCurrentPage() {
  if (!ga4?.active && !meta?.active) return
  const path = window.location.pathname + window.location.search
  if (path === lastViewed) return
  lastViewed = path
  ga4?.pageView(path, document.title)
  meta?.pageView()
}

function apply(snap) {
  ga4.applyConsent(snap.analytics)
  // snap.marketing is already false while Global Privacy Control is on.
  if (needsReload({ linkedin, meta }, snap.marketing)) {
    meta.applyConsent(false) // revoke + delete _fbp/_fbc before reloading
    window.location.reload()
    return
  }
  linkedin.applyConsent(snap.marketing)
  meta.applyConsent(snap.marketing)
  if (!ga4.active && !meta.active) lastViewed = null
  viewCurrentPage()
}

// Connects optional third-party measurement to Studio settings (public
// settings `tracking`: only configured IDs are present) and to consent.
// Renders nothing. Every integration is inactive without its ID and runs
// only while its consent category is granted (utils/consent.js):
// GA4 -> Analytics; LinkedIn Insight Tag and Meta Pixel -> Marketing.
export default function TrackingManager() {
  const tracking = useSelector((s) => s.site.settings?.tracking)
  const { pathname, search } = useLocation()
  const gaId = tracking?.ga4MeasurementId || null
  const linkedinId = tracking?.linkedinPartnerId || null
  const metaId = tracking?.metaPixelId || null

  useEffect(() => {
    if (!browser) return undefined
    ga4.configure(gaId)
    linkedin.configure(linkedinId)
    meta.configure(metaId)
    apply(consentSnapshot())
    return onConsentChange(apply)
  }, [gaId, linkedinId, metaId])

  useEffect(() => {
    viewCurrentPage()
  }, [pathname, search])

  return null
}
