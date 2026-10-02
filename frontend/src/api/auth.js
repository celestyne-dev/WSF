import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'

// The mock admin users list is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockAdmin
async function loadMockAdmin() {
  if (!_mockAdmin) _mockAdmin = await import('../mock/admin')
  return _mockAdmin
}

// `role` (singular) stays for the header's own display and existing
// callers — the FIRST role only, same as before. `roles`/`permissions`
// are the full sets, needed for the permission-gated Users/Roles nav
// items (see utils/permissions.js) — a staff member can legitimately
// hold more than one role (e.g. editor + partnerships_manager), and a
// UI check must see all of them, not just the first.
function mapUser(u) {
  if (!u) return null
  const roles = (u.roles || []).map((r) => r.name)
  const permissions = [...new Set((u.roles || []).flatMap((r) => (r.permissions || []).map((p) => p.name)))]
  return {
    id: u.id,
    name: u.full_name || `${u.first_name} ${u.last_name}`.trim(),
    email: u.email,
    role: roles[0] || 'member',
    roles,
    permissions,
    // True from staff creation or an admin password reset until this user
    // completes POST /auth/change-password herself — see backend
    // app/auth/decorators.py, which rejects every permission/role-gated
    // request while this is true, so the frontend redirect below is a
    // convenience, not the enforcement.
    mustChangePassword: !!u.must_change_password,
  }
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
      return { success: true, accessToken: data.access_token, refreshToken: data.refresh_token, user: mapUser(data.user) }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Invalid email or password.' }
    }
  }
  const { adminUsers } = await loadMockAdmin()
  const user = adminUsers.find((u) => u.email.toLowerCase() === email.toLowerCase())
  if (!user || password.length < 4) {
    return delay({ success: false, message: 'Invalid email or password.' }, 400)
  }
  return delay(
    {
      success: true,
      accessToken: `mock-jwt-${user.id}`,
      refreshToken: null,
      user: mapMockUser(user),
    },
    400,
  )
}

// Mock mode has no per-role permission list (that's backend-seeded data —
// see app/services/rbac.py) — `super_admin` is treated the same
// always-allowed way the real backend's "*" grant works, so the
// permission-gated Users/Roles nav item still demos correctly; every
// other mock role simply won't see it, same as a real account without
// users.view/users.manage/roles.manage.
function mapMockUser(user) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
    roles: [user.role],
    permissions: user.role === 'super_admin' ? ['*'] : [],
    // Mock mode has no temporary-password/admin-reset flow to simulate.
    mustChangePassword: false,
  }
}

// POST /api/v1/auth/change-password — resolves (never throws) with
// { success, user? } | { success, message, code? }, same never-throw
// convention as login() above, so the page can render a field-level or
// toast error without a try/catch of its own. Not available in mock mode —
// mock accounts never carry mustChangePassword and have no backend to
// verify a current password against.
export async function changePassword({ currentPassword, newPassword, confirmPassword }) {
  if (USE_MOCK) {
    return { success: false, message: 'Password changes are not available in demo mode.' }
  }
  try {
    const { data } = await apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    })
    return { success: true, user: mapUser(data) }
  } catch (err) {
    return {
      success: false,
      message: err.apiError?.message || 'Could not change your password. Please try again.',
      code: err.apiError?.code,
    }
  }
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
  const { adminUsers } = await loadMockAdmin()
  const userId = token?.replace('mock-jwt-', '')
  const user = adminUsers.find((u) => u.id === userId)
  return delay(user ? mapMockUser(user) : null)
}
