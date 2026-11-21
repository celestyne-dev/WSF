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

export const CONSENT_STORAGE_KEY = 'wsf_cookie_consent'
export const OPTIONAL_CATEGORIES = ['preferences', 'analytics', 'marketing']

let storage = typeof window !== 'undefined' ? safeLocalStorage() : null
// The server writes the configured version onto <html> (spa_shell), so an
// existing choice applies on the very first render, before /public/settings.
let configuredVersion = readServerVersion()
let memoryChoice = null // used when storage is unavailable (private mode)
const listeners = new Set()
const openListeners = new Set()

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
  return choice && choice.version === configuredVersion ? choice : null
}

export function needsConsentDecision() {
  return Boolean(configuredVersion) && getConsent() === null
}

export function hasConsent(category) {
  if (category === 'essential') return true
  if (!OPTIONAL_CATEGORIES.includes(category)) return false
  const choice = getConsent()
  return Boolean(choice && choice[category] === true)
}

export function saveConsent(choices, now = new Date()) {
  if (!configuredVersion) return null
  const record = {
    version: configuredVersion,
    timestamp: now.toISOString(),
    ...Object.fromEntries(OPTIONAL_CATEGORIES.map((c) => [c, choices?.[c] === true])),
  }
  memoryChoice = record
  try {
    storage?.setItem(CONSENT_STORAGE_KEY, JSON.stringify(record))
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
  notify()
  return record
}

export const acceptAllConsent = (now) => saveConsent({ preferences: true, analytics: true, marketing: true }, now)
export const rejectOptionalConsent = (now) => saveConsent({ preferences: false, analytics: false, marketing: false }, now)

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
    ...Object.fromEntries(OPTIONAL_CATEGORIES.map((c) => [c, Boolean(choice && choice[c])])),
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
