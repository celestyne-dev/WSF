// Minimum signup age (Step 18). The server (app/services/account_policy.py)
// owns the value and the check; this only words the checkbox. Falls back to
// the approved default of 16 when settings haven't loaded or are malformed.
export const DEFAULT_MINIMUM_AGE = 16

export function minimumAgeOf(settings) {
  const age = settings?.accountPolicy?.minimumAge
  return Number.isInteger(age) && age >= DEFAULT_MINIMUM_AGE && age <= 21 ? age : DEFAULT_MINIMUM_AGE
}

export function ageConfirmationLabel(age) {
  return `I confirm that I am at least ${age} years old.`
}

// Only an explicit tick counts — the request carries JSON true, never a
// string, and the server rejects anything else before storing the account.
export function registerAgePayload(confirmed) {
  return { age_confirmed: confirmed === true }
}
