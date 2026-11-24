// The previous auth design kept both JWTs in localStorage. They are deleted
// on every page load and never read: members sign in once after the change
// to the HttpOnly refresh cookie.
export const LEGACY_TOKEN_KEYS = ['wsf_access_token', 'wsf_refresh_token']

export function purgeLegacyTokens(storage) {
  let removed = 0
  for (const key of LEGACY_TOKEN_KEYS) {
    try {
      if (storage?.getItem(key) !== null && storage?.getItem(key) !== undefined) removed += 1
      storage?.removeItem(key)
    } catch {
      /* storage unavailable: nothing stored */
    }
  }
  return removed
}
