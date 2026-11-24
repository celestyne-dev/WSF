import { apiClient, USE_MOCK } from './client'

// Two-factor authentication (backend app/api/v1/two_factor.py). Sign-in
// steps pass the short-lived `token` from POST /auth/login; account settings
// use the signed-in session instead (no token).

function failure(err, fallback) {
  return { success: false, message: err.apiError?.message || fallback, code: err.apiError?.code }
}

export async function submitTwoFactorChallenge({ token, code, recoveryCode }) {
  try {
    const body = recoveryCode ? { token, recovery_code: recoveryCode } : { token, code }
    const { data } = await apiClient.post('/auth/2fa/challenge', body, { withCredentials: true })
    return { success: true, data }
  } catch (err) {
    return failure(err, 'That code did not work. Please try again.')
  }
}

export async function startTwoFactorSetup({ token } = {}) {
  if (USE_MOCK) return { success: false, message: 'Two-factor authentication is not available in demo mode.' }
  try {
    const { data } = await apiClient.post('/auth/2fa/setup/start', token ? { token } : {})
    return { success: true, data: { secret: data.secret, otpauthUri: data.otpauth_uri, qrSvg: data.qr_svg } }
  } catch (err) {
    return failure(err, 'Could not start two-factor set-up.')
  }
}

export async function confirmTwoFactorSetup({ token, code }) {
  try {
    const { data } = await apiClient.post('/auth/2fa/setup/confirm', token ? { token, code } : { code }, { withCredentials: true })
    return { success: true, data }
  } catch (err) {
    return failure(err, 'That code did not work. Please try again.')
  }
}

export async function fetchTwoFactorStatus() {
  if (USE_MOCK) return { enabled: false, required: false, recoveryCodesRemaining: 0 }
  const { data } = await apiClient.get('/auth/2fa')
  return { enabled: data.enabled, required: data.required, recoveryCodesRemaining: data.recovery_codes_remaining }
}

export async function regenerateRecoveryCodes({ code }) {
  try {
    const { data } = await apiClient.post('/auth/2fa/recovery-codes', { code })
    return { success: true, codes: data.recovery_codes }
  } catch (err) {
    return failure(err, 'Could not create new recovery codes.')
  }
}

export async function disableTwoFactor({ password, code }) {
  try {
    await apiClient.post('/auth/2fa/disable', { password, code })
    return { success: true }
  } catch (err) {
    return failure(err, 'Could not turn off two-factor authentication.')
  }
}

export async function adminResetTwoFactor(userId) {
  try {
    const { data } = await apiClient.post(`/admin/users/${userId}/two-factor/reset`)
    return { success: true, data }
  } catch (err) {
    return failure(err, 'Could not reset two-factor authentication.')
  }
}
