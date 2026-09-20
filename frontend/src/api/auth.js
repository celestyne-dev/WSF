import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { adminUsers } from '../mock/admin'

// POST /api/v1/auth/login — Flask-JWT-Extended returns { access_token, refresh_token, user }
export async function login({ email, password }) {
  if (!USE_MOCK) return (await apiClient.post('/auth/login', { email, password })).data
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
  if (!USE_MOCK) return (await apiClient.get('/auth/me')).data
  const userId = token?.replace('mock-jwt-', '')
  const user = adminUsers.find((u) => u.id === userId)
  return delay(user ? { id: user.id, name: user.name, email: user.email, role: user.role } : null)
}
