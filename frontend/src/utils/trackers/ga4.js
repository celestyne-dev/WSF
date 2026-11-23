// Google Analytics 4, behind Analytics consent. INACTIVE unless a
// Measurement ID is configured in Studio (Settings -> Integrations).
//
//   No ID                         nothing at all: no script, no request,
//                                 no dataLayer, no cookie.
//   ID, no Analytics consent      Consent Mode v2 defaults are queued in
//                                 window.dataLayer (all four signals
//                                 "denied"); no script, no request.
//   ID + Analytics consent        gtag.js loads from Google's fixed URL;
//                                 analytics_storage is granted. The ad_*
//                                 signals stay denied, and Google Signals
//                                 and ad personalization are switched off.
//   Consent withdrawn             analytics_storage denied, the official
//                                 ga-disable flag stops all hits, and the
//                                 site's own _ga / _ga_* cookies are deleted.
//                                 Re-granting resumes measurement.
//
// Only _ga and _ga_* cookies on this site's own host and parent domains are
// removed; cookies of other sites are unreachable by design.

const SCRIPT_BASE = 'https://www.googletagmanager.com/gtag/js?id='
export const GA_ID_PATTERN = /^G-[A-Z0-9]{4,20}$/

const DENIED_DEFAULTS = {
  ad_storage: 'denied',
  analytics_storage: 'denied',
  ad_user_data: 'denied',
  ad_personalization: 'denied',
}

export function createGa4({ win = window, doc = document } = {}) {
  let id = null
  let loaded = false
  let granted = false

  function gtag() {
    // gtag.js requires the arguments object itself, not an array.
    // eslint-disable-next-line prefer-rest-params
    win.dataLayer.push(arguments)
  }

  function ensureQueue() {
    if (win.dataLayer) return
    win.dataLayer = []
    win.gtag = gtag
    gtag('consent', 'default', { ...DENIED_DEFAULTS })
  }

  function loadScript() {
    if (loaded) return
    loaded = true
    const script = doc.createElement('script')
    script.async = true
    script.src = SCRIPT_BASE + encodeURIComponent(id)
    script.dataset.wsfTracker = 'ga4'
    doc.head.appendChild(script)
    gtag('js', new Date())
    gtag('config', id, {
      send_page_view: false, // page views are sent per SPA route change
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
    })
  }

  return {
    get active() {
      return Boolean(id) && granted
    },
    get scriptLoaded() {
      return loaded
    },
    /** Measurement ID from public settings; anything invalid = inactive. */
    configure(measurementId) {
      const next = typeof measurementId === 'string' && GA_ID_PATTERN.test(measurementId) ? measurementId : null
      if (id && next !== id) {
        // Turned off or changed in Studio: stop the old one for this page.
        win[`ga-disable-${id}`] = true
        granted = false
      }
      id = next
      if (id) ensureQueue()
    },
    /** Called with the current Analytics consent on every change. */
    applyConsent(analytics) {
      if (!id) return
      if (analytics) {
        win[`ga-disable-${id}`] = false
        gtag('consent', 'update', { analytics_storage: 'granted' })
        granted = true
        loadScript()
      } else {
        if (granted || loaded) {
          gtag('consent', 'update', { analytics_storage: 'denied' })
          win[`ga-disable-${id}`] = true
        }
        granted = false
        deleteGaCookies(doc, win.location?.hostname)
      }
    },
    pageView(path, title) {
      if (!this.active) return
      gtag('event', 'page_view', { page_path: path, page_location: win.location?.href, page_title: title })
    },
  }
}

/** Domains a first-party cookie for `hostname` may have been set on:
 * the host itself and each parent (never a bare TLD). */
export function cookieDomainsFor(hostname) {
  if (!hostname || /^[\d.]+$/.test(hostname) || !hostname.includes('.')) return [null]
  const parts = hostname.split('.')
  const domains = [null]
  for (let i = 0; i < parts.length - 1; i += 1) domains.push(`.${parts.slice(i).join('.')}`)
  return domains
}

export function gaCookieNames(cookieString) {
  return (cookieString || '')
    .split(';')
    .map((c) => c.split('=')[0].trim())
    .filter((name) => name === '_ga' || name.startsWith('_ga_'))
}

export function deleteGaCookies(doc, hostname) {
  const names = gaCookieNames(doc.cookie)
  for (const name of names) {
    for (const domain of cookieDomainsFor(hostname)) {
      doc.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domain ? `; domain=${domain}` : ''}`
    }
  }
  return names
}
