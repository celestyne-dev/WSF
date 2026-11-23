// Sends each distinct consent decision of a signed-in member to the server
// once. A decision is identified by (user, consent version, decision time),
// the same identity the server uses to ignore repeats, so a reload, a second
// tab or signing in after deciding never creates duplicate history rows.
// Anonymous visitors are never sent anything.
// The payload is the EFFECTIVE choice (getConsent() is already normalized
// for Global Privacy Control); Marketing is forced false again here as a
// last guard so a GPC browser can never report Marketing=true.
export function effectiveChoice(choice, gpc) {
  if (!choice) return null
  return gpc && choice.marketing ? { ...choice, marketing: false } : choice
}

export function createConsentSync(send) {
  let lastKey = null
  return function sync({ userId, choice: rawChoice, gpc = false }) {
    const choice = effectiveChoice(rawChoice, gpc)
    if (!userId || !choice) return false
    const key = `${userId}|${choice.version}|${choice.timestamp}`
    if (key === lastKey) return false
    lastKey = key
    Promise.resolve()
      .then(() => send(choice))
      .catch(() => {
        // Not recorded this time (offline, expired session): allow a retry
        // on the next change instead of pretending it was stored.
        if (lastKey === key) lastKey = null
      })
    return true
  }
}
