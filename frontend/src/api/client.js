import axios from 'axios'
import { purgeLegacyTokens } from '../utils/legacyTokens'

// Real backend base URL. Every endpoint below is namespaced to mirror the
// eventual Flask API exactly (e.g. GET /api/v1/articles/{slug}), even though
// the mock implementations don't hit the network yet. When USE_MOCK is false
// (the default — see below), each resource module calls through this
// client with zero changes to the components that consume it.
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

// ---- Session tokens ----------------------------------------------------------------------
// The access token lives ONLY in this module's memory (never localStorage,
// sessionStorage or a cookie): a reload drops it and the app gets a new one
// from the HttpOnly refresh cookie (refreshSession below). JavaScript never
// sees the refresh credential.
let accessToken = null
let sessionListener = null

export function getAccessToken() {
  return accessToken
}

export function setAccessToken(token) {
  accessToken = token || null
}

/** Called with the new token (or null) whenever the client itself changes
 * it (a 401 recovered by refresh, or a session that could not be
 * recovered), so the auth store stays in step. */
export function setSessionListener(fn) {
  sessionListener = fn
}

function changeToken(token) {
  setAccessToken(token)
  try {
    sessionListener?.(accessToken)
  } catch {
    /* the store must not break the API client */
  }
}

// Tokens from the old design (localStorage) are deleted on load and never
// reused (utils/legacyTokens.js).
try {
  purgeLegacyTokens(typeof window !== 'undefined' ? window.localStorage : null)
} catch {
  /* storage unavailable */
}

export function clearStoredAuth() {
  changeToken(null)
}

// The one endpoint the HttpOnly refresh cookie is sent to (its Path). Every
// call carries the CSRF header the server requires.
export const CSRF_HEADER = { 'X-WSF-CSRF': '1' }

/** POST /auth/refresh with the cookie: {accessToken, user(raw)} or null
 * when this browser has no valid session. Never throws for "signed out". */
export async function refreshSession() {
  try {
    const response = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, null, {
      headers: CSRF_HEADER,
      withCredentials: true,
    })
    const data = response.data?.data
    if (!data?.access_token) {
      changeToken(null)
      return null
    }
    changeToken(data.access_token)
    return { accessToken: data.access_token, user: data.user }
  } catch {
    changeToken(null)
    return null
  }
}

/** DELETE /auth/refresh: revokes this browser's session server-side, clears
 * the cookie and blocks the current access token. */
export async function endSession() {
  const token = accessToken
  changeToken(null)
  try {
    await axios.delete(`${apiClient.defaults.baseURL}/auth/refresh`, {
      headers: { ...CSRF_HEADER, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      withCredentials: true,
    })
  } catch {
    /* signed out locally either way; the server session expires on its own */
  }
}

// Requests made while the startup silent refresh is still running wait for
// it, so a hard-loaded page (e.g. a Paystack callback) sends its first API
// call already authenticated instead of collecting a 401 first.
let sessionReady = Promise.resolve()
export function waitForSession(promise) {
  sessionReady = Promise.resolve(promise).catch(() => null)
  return sessionReady
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
apiClient.interceptors.request.use(async (config) => {
  await sessionReady
  const token = accessToken
  if (token && !config.headers?.Authorization) {
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
// is routine during a normal admin session, not just at startup). The
// HttpOnly refresh cookie (30-day session) recovers it silently exactly
// once before giving up, rather than leaving the
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
  const session = await refreshSession()
  if (!session) throw new Error('No session to refresh.')
  return session.accessToken
}

function redirectToLogin() {
  clearStoredAuth()
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
}

// Same effect on stored auth state as redirectToLogin(), but never
// navigates — used only when the failing request opted out of the hard
// redirect via `suppressAuthRedirect` (see handleUnauthorized below), so
// the page that made the request can render its own "sign in" state with
// its own preserved return path, rather than being yanked to bare /login
// mid-render with that return path lost. The original 401 is still
// rejected either way — this only ever changes whether a navigation
// happens, never whether the request succeeds or whether stored tokens
// get cleared.
function clearAuthWithoutRedirect() {
  clearStoredAuth()
}

async function handleUnauthorized(error) {
  const originalRequest = error.config || {}
  const url = originalRequest.url || ''
  const isLoginAttempt = url.includes('/auth/login')
  const isRefreshAttempt = url.includes('/auth/refresh')
  // Opt-in only (see api/resources.js's getResourcePaymentStatus for the
  // one caller that currently sets this) — every other request leaves
  // this undefined and gets the exact redirectToLogin() behavior below
  // that's always existed.
  const suppressRedirect = !!originalRequest.suppressAuthRedirect
  const giveUp = suppressRedirect ? clearAuthWithoutRedirect : redirectToLogin

  if (isLoginAttempt) {
    return Promise.reject(error)
  }
  if (isRefreshAttempt || originalRequest._retriedAfterRefresh) {
    // The refresh token itself is invalid/expired, or a request we already
    // retried once with a fresh access token still failed — no further
    // recovery is possible.
    giveUp()
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
    giveUp()
    return Promise.reject(error)
  }
}

// Fail-closed by design: mock mode is an explicit opt-in (VITE_USE_MOCK must
// be exactly the string "true"), never the default. An unset, misspelled,
// or empty VITE_USE_MOCK — e.g. a production build whose .env was never
// updated — resolves to `false` and talks to the real backend, rather than
// silently serving fake data and (per api/auth.js) disabling account
// management with a "not available in demo mode" message. Local development
// still opts into mock mode the same way it always has: set
// VITE_USE_MOCK=true in frontend/.env (see .env.example).
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
