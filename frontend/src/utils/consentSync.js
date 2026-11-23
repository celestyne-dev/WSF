// Sends each distinct consent decision of a signed-in member to the server
// once. A decision is identified by (user, consent version, decision time),
// the same identity the server uses to ignore repeats, so a reload, a second
// tab or signing in after deciding never creates duplicate history rows.
// Anonymous visitors are never sent anything.
export function createConsentSync(send) {
  let lastKey = null
  return function sync({ userId, choice }) {
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
