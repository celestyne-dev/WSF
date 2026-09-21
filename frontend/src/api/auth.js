import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { adminUsers } from '../mock/admin'

function mapUser(u) {
  if (!u) return null
  return { id: u.id, name: u.full_name || `${u.first_name} ${u.last_name}`.trim(), email: u.email, role: u.roles?.[0]?.name || 'member' }
}

// POST /api/v1/auth/login — Flask-JWT-Extended returns { access_token, refresh_token, user }.
// authSlice.js expects login() to always RESOLVE (never throw) with
// { success, message? } | { success, accessToken, user } — a failed login
// is data, not an exception, so a 401 from the real backend is caught and
// normalized into that same shape rather than rejecting the thunk oddly.
export async function login({ email, password }) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/auth/login', { email, password })
      return { success: true, accessToken: data.access_token, user: mapUser(data.user) }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Invalid email or password.' }
    }
  }
  const user = adminUsers.find((u) => u.email.toLowerCase() === email.toLowerCase())
  if (!user || password.length < 4) {
    return delay({ success: false, message: 'Invalid email or password.' }, 400)
  }
  return delay(
    {
      success: true,
      accessToken: `mock-jwt-${user.id}`,
      user: { id: user.id, name: user.name, email: user.email, role: user.role },
    },
    400,
  )
}

export async function fetchCurrentUser(token) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get('/auth/me')
      return mapUser(data)
    } catch {
      return null
    }
  }
  const userId = token?.replace('mock-jwt-', '')
  const user = adminUsers.find((u) => u.id === userId)
  return delay(user ? { id: user.id, name: user.name, email: user.email, role: user.role } : null)
}
