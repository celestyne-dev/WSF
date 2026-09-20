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

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
