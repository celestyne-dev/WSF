// LinkedIn-first acquisition tracking.
//
// Women Shaping Futures' primary audience-acquisition channel is LinkedIn:
// LinkedIn -> article -> more content -> newsletter -> resource/event/
// product/community. This module captures where a visitor came from
// (LinkedIn, another referrer, or a UTM-tagged campaign link) once per
// session and makes it available to attach to every conversion event —
// newsletter signups, resource downloads, event registrations, job/
// opportunity clicks, and partnership enquiries — without ever mutating
// the canonical URL (UTM params are read from the query string, not
// persisted into `<link rel="canonical">`, so they never create duplicate
// canonical URLs or duplicate content for search engines).
//
// In real (non-mock) mode this same shape (`acquisition` on every event
// payload) flows to `POST /api/v1/analytics/events`, which is what powers
// referral-source breakdowns in the admin Analytics screen. Nothing here
// talks to LinkedIn's API — the site's own funnel works whether or not
// that integration ever exists.

import { apiClient, USE_MOCK } from '../api/client'

const STORAGE_KEY = 'wsf_acquisition'
const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']

function readStored() {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeStored(context) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(context))
  } catch {
    // sessionStorage unavailable (private browsing, etc.) — tracking is best-effort.
  }
}

function sourceFromReferrer(referrer) {
  if (!referrer) return null
  try {
    const url = new URL(referrer)
    if (url.hostname === window.location.hostname) return null // internal navigation, not a new touch
    if (/linkedin\.com$/.test(url.hostname.replace(/^www\./, ''))) return 'linkedin'
    return url.hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

/**
 * Reads UTM params and the document referrer, and records the visitor's
 * acquisition source for this browser session. Safe to call on every
 * route change — internal navigation without new UTM params or an
 * external referrer leaves the existing (first-touch) attribution intact.
 */
export function captureAcquisitionContext() {
  if (typeof window === 'undefined') return null

  const params = new URLSearchParams(window.location.search)
  const utm = Object.fromEntries(UTM_KEYS.map((k) => [k, params.get(k)]).filter(([, v]) => v))
  const referredSource = sourceFromReferrer(document.referrer)
  const isNewTouch = Boolean(utm.utm_source || referredSource)

  const existing = readStored()
  if (!isNewTouch && existing) return existing

  const source = utm.utm_source || referredSource || existing?.source || 'direct'
  const context = {
    source,
    medium: utm.utm_medium || (source === 'linkedin' ? 'social' : existing?.medium || 'none'),
    campaign: utm.utm_campaign || existing?.campaign || null,
    content: utm.utm_content || existing?.content || null,
    term: utm.utm_term || existing?.term || null,
    referrer: document.referrer || existing?.referrer || null,
    landingPath: existing?.landingPath || window.location.pathname,
    capturedAt: existing?.capturedAt || new Date().toISOString(),
  }
  writeStored(context)
  return context
}

export function getAcquisitionContext() {
  return readStored()
}

export function isFromLinkedIn() {
  return readStored()?.source === 'linkedin'
}

/** Attaches the session's acquisition context to a form/API payload. */
export function withAcquisitionMetadata(payload = {}) {
  return { ...payload, acquisition: getAcquisitionContext() }
}

/**
 * Records a conversion or engagement event (newsletter signup, resource
 * download, event registration, job/opportunity click, partnership
 * enquiry, ...) tagged with the visitor's acquisition source. Logs to the
 * console in development; when running against the real backend it also
 * posts to POST /api/v1/analytics/events (fire-and-forget — a dropped
 * analytics beacon should never block or break the visitor's action).
 */
export function trackEvent(eventName, payload = {}) {
  const acquisition = getAcquisitionContext()
  const event = {
    event: eventName,
    ...payload,
    acquisition,
    path: typeof window !== 'undefined' ? window.location.pathname : null,
    timestamp: new Date().toISOString(),
  }
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.debug('[analytics]', event)
  }
  if (!USE_MOCK) {
    apiClient.post('/analytics/events', { eventName, payload, acquisition }).catch(() => {})
  }
  return event
}
