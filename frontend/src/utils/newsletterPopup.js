// Pure rules for the WSF Weekly popup (component: components/newsletter/
// NewsletterPopup.jsx). Settings come from Studio (Settings -> Newsletter
// popup, backend engagement_settings.py).

export const POPUP_STORAGE_KEY = 'wsf_newsletter_popup'
const DAY_MS = 24 * 60 * 60 * 1000

// Never opened automatically where it would interrupt a task: Studio, sign-in
// and account flows, newsletter pages, legal pages, checkout callbacks,
// certificate verification, forms, purchase pages and lesson reading.
const EXCLUDED_PREFIXES = [
  '/admin', '/login', '/register', '/forgot-password', '/reset-password', '/change-password', '/account',
  '/newsletter', '/privacy', '/terms', '/cookies', '/editorial-policy', '/certificates/verify',
  '/submit', '/nominate', '/directory/submit', '/contact', '/lifetime', '/circle',
]
const EXCLUDED_PATTERNS = [/\/checkout\/callback(\/|$)/, /^\/learning\/[^/]+\/lessons\//]

export function isPopupExcludedPath(path) {
  const p = (path || '/').split('?')[0].replace(/\/+$/, '') || '/'
  if (EXCLUDED_PATTERNS.some((re) => re.test(p))) return true
  return EXCLUDED_PREFIXES.some((prefix) => p === prefix || p.startsWith(`${prefix}/`))
}

/** {dismissedAt?, subscribedAt?} ISO strings, or {} for anything unusable. */
export function readPopupState(storage) {
  try {
    const raw = storage?.getItem(POPUP_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : null
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

export function writePopupState(storage, state) {
  try {
    storage?.setItem(POPUP_STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* storage unavailable: suppression lasts for this page only */
  }
}

// Where the popup's own state lives depends on Preferences consent:
//   granted      -> localStorage   (remembered across visits for the
//                                   dismissDays / successDays windows)
//   not granted  -> sessionStorage (this browser tab session only)
// Showing the popup and signing up never depend on this; only how long
// "closed" / "signed up" is remembered does.
export function popupStorageFor(preferencesGranted, { local, session }) {
  return preferencesGranted ? local : session
}

/** Moves the popup state to the storage the current Preferences choice
 * allows. Withdrawing (or never giving) Preferences removes the persistent
 * copy and keeps a session-only one, so the popup doesn't reappear in the
 * same session; granting it carries the session state into localStorage. */
export function syncPopupStorage(preferencesGranted, { local, session }) {
  const from = preferencesGranted ? session : local
  const to = preferencesGranted ? local : session
  try {
    const raw = from?.getItem(POPUP_STORAGE_KEY)
    if (raw && !to?.getItem(POPUP_STORAGE_KEY)) to?.setItem(POPUP_STORAGE_KEY, raw)
    from?.removeItem(POPUP_STORAGE_KEY)
  } catch {
    /* storage unavailable: nothing persisted */
  }
}

function within(iso, days, now) {
  const t = Date.parse(iso)
  return Number.isFinite(t) && now - t < days * DAY_MS
}

export function isPopupSuppressed(state, settings, now = Date.now()) {
  if (state?.subscribedAt && within(state.subscribedAt, settings.successDays, now)) return true
  if (state?.dismissedAt && within(state.dismissedAt, settings.dismissDays, now)) return true
  return false
}

/** Fires on whichever comes first: time on the site, or scroll depth on the
 * current page. A threshold of 0 disables that trigger. */
export function popupTriggerReached({ elapsedMs, scrollPercent }, settings) {
  const byTime = settings.delaySeconds > 0 && elapsedMs >= settings.delaySeconds * 1000
  const byScroll = settings.scrollPercent > 0 && scrollPercent >= settings.scrollPercent
  return byTime || byScroll
}

export function scrollPercentOf(win = window, doc = document) {
  const max = Math.max(doc.documentElement.scrollHeight - win.innerHeight, 0)
  if (max === 0) return 0
  return Math.min(100, Math.round((win.scrollY / max) * 100))
}
