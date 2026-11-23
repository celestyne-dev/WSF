// LinkedIn Insight Tag and Meta Pixel, behind MARKETING consent. Each is
// INACTIVE unless its ID is configured in Studio (Settings -> Integrations),
// and never runs while the browser sends Global Privacy Control (consent.js
// reports Marketing as not granted then).
//
//   No ID, or no Marketing consent   nothing: no global, no script, no
//                                    request, no storage.
//   ID + Marketing consent           the provider's script loads once from
//                                    its fixed official URL.
//   Marketing withdrawn              Meta: fbq('consent', 'revoke') and the
//                                    site's _fbp / _fbc cookies are deleted.
//                                    LinkedIn's tag has no off switch, so the
//                                    caller reloads the page (needsReload) to
//                                    unload whatever was loaded.

import { cookieDomainsFor } from './ga4.js'

const LINKEDIN_SCRIPT = 'https://snap.licdn.com/li.lms-analytics/insight.min.js'
const META_SCRIPT = 'https://connect.facebook.net/en_US/fbevents.js'
export const LINKEDIN_ID_PATTERN = /^[0-9]{4,12}$/
export const META_ID_PATTERN = /^[0-9]{6,20}$/

function appendScript(doc, src, name) {
  const script = doc.createElement('script')
  script.async = true
  script.src = src
  script.dataset.wsfTracker = name
  doc.head.appendChild(script)
}

export function createLinkedInInsight({ win = window, doc = document } = {}) {
  let id = null
  let loaded = false
  return {
    get loaded() {
      return loaded
    },
    configure(partnerId) {
      id = typeof partnerId === 'string' && LINKEDIN_ID_PATTERN.test(partnerId) ? partnerId : null
    },
    applyConsent(marketing) {
      if (!id || !marketing || loaded) return
      loaded = true
      win._linkedin_partner_id = id
      win._linkedin_data_partner_ids = win._linkedin_data_partner_ids || []
      win._linkedin_data_partner_ids.push(id)
      appendScript(doc, LINKEDIN_SCRIPT, 'linkedin-insight')
    },
  }
}

export function createMetaPixel({ win = window, doc = document } = {}) {
  let id = null
  let loaded = false
  let granted = false

  function installQueue() {
    // The standard fbq command queue, without the inline snippet.
    const fbq = function fbqQueue(...args) {
      if (fbq.callMethod) fbq.callMethod(...args)
      else fbq.queue.push(args)
    }
    fbq.push = fbq
    fbq.loaded = true
    fbq.version = '2.0'
    fbq.queue = []
    win.fbq = fbq
    if (!win._fbq) win._fbq = fbq
  }

  return {
    get loaded() {
      return loaded
    },
    get active() {
      return Boolean(id) && granted
    },
    configure(pixelId) {
      id = typeof pixelId === 'string' && META_ID_PATTERN.test(pixelId) ? pixelId : null
    },
    applyConsent(marketing) {
      if (!id) return
      if (marketing) {
        granted = true
        if (!loaded) {
          loaded = true
          installQueue()
          win.fbq('consent', 'grant')
          // No automatic collection of button text / page metadata.
          win.fbq('set', 'autoConfig', false, id)
          win.fbq('init', id)
          appendScript(doc, META_SCRIPT, 'meta-pixel')
        } else {
          win.fbq('consent', 'grant')
        }
      } else {
        if (loaded && granted) win.fbq('consent', 'revoke')
        granted = false
        deleteMetaCookies(doc, win.location?.hostname)
      }
    },
    pageView() {
      if (this.active) win.fbq('track', 'PageView')
    },
  }
}

export function deleteMetaCookies(doc, hostname) {
  const names = (doc.cookie || '')
    .split(';')
    .map((c) => c.split('=')[0].trim())
    .filter((name) => name === '_fbp' || name === '_fbc')
  for (const name of names) {
    for (const domain of cookieDomainsFor(hostname)) {
      doc.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domain ? `; domain=${domain}` : ''}`
    }
  }
  return names
}

/** A marketing script was running on this page and consent is now gone:
 * only a reload truly unloads it. */
export function needsReload({ linkedin, meta }, marketing) {
  return !marketing && Boolean(linkedin?.loaded || meta?.loaded)
}
