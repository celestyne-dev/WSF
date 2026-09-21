import axios from 'axios'

// Real backend base URL. Every endpoint below is namespaced to mirror the
// eventual Flask API exactly (e.g. GET /api/v1/articles/{slug}), even though
// the mock implementations don't hit the network yet. When USE_MOCK is
// flipped to false (or VITE_USE_MOCK=false is set), each resource module
// swaps its mock branch for a call through this client with zero changes
// to the components that consume it.
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('wsf_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
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
      if (body.meta) {
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
    return Promise.reject(error)
  },
)

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
