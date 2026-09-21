import axios from 'axios'

// Real backend base URL. Every endpoint below is namespaced to mirror the
// eventual Flask API exactly (e.g. GET /api/v1/articles/{slug}), even though
// the mock implementations don't hit the network yet. When USE_MOCK is
// flipped to false (or VITE_USE_MOCK=false is set), each resource module
// swaps its mock branch for a call through this client with zero changes
// to the components that consume it.
// No hard-coded Content-Type default: axios's own request transform sets
// application/json for a plain-object body automatically, and a hard-coded
// default here would otherwise survive untouched through a FormData upload
// (axios's FormData branch returns the body as-is without clearing an
// already-set Content-Type), leaving the browser unable to add the
// multipart boundary Flask needs to parse request.files. See the request
// interceptor below for the explicit FormData guard.
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
})

export const ACCESS_TOKEN_KEY = 'wsf_access_token'
export const REFRESH_TOKEN_KEY = 'wsf_refresh_token'

export function clearStoredAuth() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

function camelToSnake(str) {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

// Query params are built with the mock layer's camelCase field names
// (pageSize, workMode, careerLevel, employmentType, ...) since that's what
// mockUtils.js:paginate and every api/*.js filter object already use. The
// Flask backend's query-string filters are snake_case (per_page, work_mode,
// ...), and `pageSize` specifically must become `per_page` for pagination
// to work at all — translating it here, once, keeps every fetch* function
// free of that detail.
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // File uploads (media upload) pass a FormData body — it must never carry
  // an explicit Content-Type, so the browser can generate the multipart
  // boundary itself. Belt-and-suspenders alongside removing the instance
  // default above, in case any caller or future default re-adds one.
  if (config.data instanceof FormData) {
    if (typeof config.headers?.delete === 'function') {
      config.headers.delete('Content-Type')
    } else if (config.headers) {
      delete config.headers['Content-Type']
    }
  }
  if (config.params && typeof config.params === 'object') {
    const translated = {}
    for (const [key, value] of Object.entries(config.params)) {
      if (value === undefined || value === null || value === '') continue
      const backendKey = key === 'pageSize' ? 'per_page' : camelToSnake(key)
      translated[backendKey] = value
    }
    config.params = translated
  }
  return config
})

// The Flask backend wraps every response as
// {success, data, meta?} / {success: false, error: {message, code, details?}}
// (see backend/app/utils/responses.py). Every api/*.js module below was
// written against the mock layer's shapes instead — a bare array/object for
// single items and un-paginated collections, or {items, pagination:
// {page, pageSize, totalItems, totalPages}} for paginated lists (see
// mockUtils.js:paginate) — so each `!USE_MOCK` branch could do
// `const { data } = await apiClient.get(...); return data` unchanged
// whichever way this got wired up later. This interceptor is that wiring:
// it unwraps the backend's envelope into exactly those shapes, so the
// pre-written real branches work without touching them file by file.
apiClient.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && 'success' in body) {
      // A `meta` block alone doesn't mean "this is a paginated list" — a
      // detail endpoint (e.g. GET /topics/{slug}) can return a single
      // object that embeds its own paginated sub-collection (the topic's
      // articles) and still carry `meta` for THAT sub-list. Only unwrap
      // into {items, pagination} when `data` itself is actually an array;
      // otherwise a detail response's `.data` would get replaced with
      // {items: <the object>, pagination}, silently losing every field a
      // caller like mapTopic()/mapAuthor()/mapSeries() expects to read
      // directly (author.topic, .data.author, etc. all read as undefined).
      if (body.meta && Array.isArray(body.data)) {
        response.data = {
          items: body.data,
          pagination: {
            page: body.meta.page,
            pageSize: body.meta.per_page,
            totalItems: body.meta.total,
            totalPages: body.meta.total_pages,
          },
        }
      } else {
        response.data = body.data
      }
    }
    return response
  },
  (error) => {
    const body = error.response?.data
    if (body?.error) {
      error.message = body.error.message || error.message
      error.apiError = body.error
    }
    if (error.response?.status === 401) {
      return handleUnauthorized(error)
    }
    return Promise.reject(error)
  },
)

// A 401 means the access token is missing, expired, or otherwise invalid
// (JWT_ACCESS_TOKEN_EXPIRES is 30 minutes — see backend/config.py — so this
// is routine during a normal admin session, not just at startup). Flask
// issues a matching refresh token at login (30-day expiry); this recovers
// silently with it exactly once before giving up, rather than leaving the
// CMS stuck re-firing the same failed request or refreshing forever:
//   - a request that already carries a fresh access token but still 401s
//     (revoked/deactivated user, clock skew) is retried once via refresh;
//   - if the refresh call itself 401s, or a retried request 401s again,
//     the session is unrecoverable — auth state is cleared and the user is
//     sent to /login rather than shown a screen that silently keeps failing.
// Login failures are explicitly excluded: a wrong password is normal user
// error, not a broken session, and api/auth.js already turns that into
// `{success: false, message}` for the login form — this must never touch
// stored tokens or redirect out from under someone re-typing a password.
let refreshPromise = null

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
  if (!refreshToken) throw new Error('No refresh token available.')
  const response = await axios.post(
    `${apiClient.defaults.baseURL}/auth/refresh`,
    null,
    { headers: { Authorization: `Bearer ${refreshToken}` } },
  )
  const accessToken = response.data?.data?.access_token
  if (!accessToken) throw new Error('Refresh response carried no access token.')
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  return accessToken
}

function redirectToLogin() {
  clearStoredAuth()
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
}

async function handleUnauthorized(error) {
  const originalRequest = error.config || {}
  const url = originalRequest.url || ''
  const isLoginAttempt = url.includes('/auth/login')
  const isRefreshAttempt = url.includes('/auth/refresh')

  if (isLoginAttempt) {
    return Promise.reject(error)
  }
  if (isRefreshAttempt || originalRequest._retriedAfterRefresh) {
    // The refresh token itself is invalid/expired, or a request we already
    // retried once with a fresh access token still failed — no further
    // recovery is possible.
    redirectToLogin()
    return Promise.reject(error)
  }

  originalRequest._retriedAfterRefresh = true
  try {
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null
      })
    }
    const accessToken = await refreshPromise
    originalRequest.headers = originalRequest.headers || {}
    originalRequest.headers.Authorization = `Bearer ${accessToken}`
    return apiClient(originalRequest)
  } catch {
    redirectToLogin()
    return Promise.reject(error)
  }
}

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
