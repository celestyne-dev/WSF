// The ONE consent boundary for optional browser technologies.
//
// Categories: essential (always on; cannot be refused), preferences,
// analytics, marketing. Every optional integration asks
// hasConsent('<category>') before running and listens with
// onConsentChange() to stop when consent is withdrawn. Nothing else in the
// app reads the stored choice directly.
//
// Stored first-party (localStorage, key below) as
//   { version, timestamp, preferences, analytics, marketing }
// No IP address, no account, no server round trip. Storing the choice is
// itself essential. A stored choice only counts while its `version` equals
// the consent version configured in Studio (Settings -> Cookie consent), so
// raising that version asks everyone again. Missing, unreadable, malformed
// or outdated data always means "no optional consent" (never yes).
//
// Global Privacy Control: while the browser sends it
// (navigator.globalPrivacyControl === true), Marketing counts as REJECTED
// and cannot be turned on; Preferences and Analytics are unaffected.
//
// A choice also EXPIRES 12 calendar months after it was made
// (CONSENT_MAX_AGE_MONTHS): an expired record is removed from storage and
// the visitor is asked again. A version change re-asks immediately, even
// before 12 months.

export const CONSENT_STORAGE_KEY = 'wsf_cookie_consent'
export const OPTIONAL_CATEGORIES = ['preferences', 'analytics', 'marketing']
export const CONSENT_MAX_AGE_MONTHS = 12

let storage = typeof window !== 'undefined' ? safeLocalStorage() : null
// The server writes the configured version onto <html> (spa_shell), so an
// existing choice applies on the very first render, before /public/settings.
let configuredVersion = readServerVersion()
let memoryChoice = null // used when storage is unavailable (private mode)
const listeners = new Set()
const openListeners = new Set()
let clock = () => new Date()
let gpcOverride = null

function readServerVersion() {
  try {
    const v = typeof document !== 'undefined' ? document.documentElement.getAttribute('data-wsf-consent-version') : null
    return v && /^[A-Za-z0-9._-]{1,20}$/.test(v) ? v : null
  } catch {
    return null
  }
}

function safeLocalStorage() {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

// Test seam: inject a Storage-like object ({getItem, setItem, removeItem}).
export function _setStorageForTests(fake) {
  storage = fake
  memoryChoice = null
  configuredVersion = null
  listeners.clear()
  openListeners.clear()
  clock = () => new Date()
  gpcOverride = null
}

// Test seam: simulate the browser's Global Privacy Control signal.
export function _setGpcForTests(value) {
  gpcOverride = value
}

/** True while the browser sends Global Privacy Control. */
export function gpcActive() {
  if (gpcOverride !== null) return gpcOverride
  try {
    return typeof navigator !== 'undefined' && navigator.globalPrivacyControl === true
  } catch {
    return false
  }
}

// Test seam: a fixed "now".
export function _setClockForTests(fn) {
  clock = fn
}

/** When a choice made at `timestamp` stops counting (12 calendar months
 * later, in UTC). Invalid timestamps count as already expired. */
export function consentExpiresAt(timestamp) {
  const made = new Date(timestamp)
  if (Number.isNaN(made.getTime())) return null
  const expires = new Date(made.getTime())
  expires.setUTCMonth(expires.getUTCMonth() + CONSENT_MAX_AGE_MONTHS)
  return expires
}

function isExpired(choice, now) {
  const expires = consentExpiresAt(choice.timestamp)
  return !expires || now.getTime() >= expires.getTime()
}

function forget() {
  memoryChoice = null
  try {
    storage?.removeItem(CONSENT_STORAGE_KEY)
  } catch {
    /* storage unavailable */
  }
}

function isChoice(value) {
  return (
    value &&
    typeof value === 'object' &&
    typeof value.version === 'string' &&
    typeof value.timestamp === 'string' &&
    OPTIONAL_CATEGORIES.every((c) => typeof value[c] === 'boolean')
  )
}

function readRaw() {
  try {
    const raw = storage ? storage.getItem(CONSENT_STORAGE_KEY) : null
    if (raw) {
      const parsed = JSON.parse(raw)
      return isChoice(parsed) ? parsed : null
    }
  } catch {
    return memoryChoice
  }
  return memoryChoice
}

/** The configured consent version (from public settings). Until it is
 * known, no optional category counts as consented. */
export function configureConsentVersion(version) {
  const next = typeof version === 'string' && version ? version : null
  if (next === configuredVersion) return
  configuredVersion = next
  notify()
}

/** The current, valid stored choice, or null when the visitor still has to
 * decide (nothing stored, malformed, or an older consent version). */
export function getConsent() {
  if (!configuredVersion) return null
  const choice = readRaw()
  if (!choice) return null
  if (isExpired(choice, clock())) {
    forget() // expired: removed, never silently renewed
    return null
  }
  return choice.version === configuredVersion ? choice : null
}

/** True once the consent version is known (from the server), i.e. once
 * "no valid choice" really means "not decided" rather than "not loaded". */
export function consentVersionKnown() {
  return Boolean(configuredVersion)
}

export function needsConsentDecision() {
  return Boolean(configuredVersion) && getConsent() === null
}

export function hasConsent(category) {
  if (category === 'essential') return true
  if (!OPTIONAL_CATEGORIES.includes(category)) return false
  if (category === 'marketing' && gpcActive()) return false
  const choice = getConsent()
  return Boolean(choice && choice[category] === true)
}

export function saveConsent(choices, now = clock()) {
  if (!configuredVersion) return null
  const record = {
    version: configuredVersion,
    timestamp: now.toISOString(),
    ...Object.fromEntries(OPTIONAL_CATEGORIES.map((c) => [c, choices?.[c] === true])),
  }
  if (gpcActive()) record.marketing = false // GPC: Marketing is recorded as rejected
  memoryChoice = record
  try {
    storage?.setItem(CONSENT_STORAGE_KEY, JSON.stringify(record))
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
  notify()
  return record
}

/** Turns one optional category on and keeps every other stored choice as it
 * is (e.g. "Always allow videos" grants Preferences only). */
export function grantConsentCategory(category, now) {
  if (!OPTIONAL_CATEGORIES.includes(category)) return null
  const current = getConsent()
  const choices = Object.fromEntries(OPTIONAL_CATEGORIES.map((c) => [c, Boolean(current?.[c])]))
  return saveConsent({ ...choices, [category]: true }, now)
}

export const acceptAllConsent = (now) => saveConsent({ preferences: true, analytics: true, marketing: true }, now)
// "Reject all": every optional category off (Essential cannot be refused).
export const rejectAllConsent = (now) => saveConsent({ preferences: false, analytics: false, marketing: false }, now)
export const rejectOptionalConsent = rejectAllConsent

/** Subscribe to consent changes; called with a snapshot
 * {preferences, analytics, marketing, decided}. Returns an unsubscribe. */
export function onConsentChange(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function snapshot() {
  const choice = getConsent()
  return {
    decided: Boolean(choice),
    gpc: gpcActive(),
    ...Object.fromEntries(OPTIONAL_CATEGORIES.map((c) => [c, hasConsent(c)])),
  }
}

function notify() {
  const snap = snapshot()
  listeners.forEach((fn) => {
    try {
      fn(snap)
    } catch {
      /* one listener must not break the others */
    }
  })
}

export const consentSnapshot = snapshot

/** Footer "Cookie settings" (or any control) reopens the manager. */
export function openConsentManager() {
  openListeners.forEach((fn) => fn())
}

export function onOpenConsentManager(listener) {
  openListeners.add(listener)
  return () => openListeners.delete(listener)
}
