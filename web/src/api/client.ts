import axios from 'axios'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Automatically inject novel_id query param and auth token
client.interceptors.request.use((config) => {
  try {
    const novelStore = useNovelStore()
    if (novelStore.activeNovelId) {
      config.params = {
        ...config.params,
        novel_id: novelStore.activeNovelId,
      }
    }
  } catch {
    // Pinia not ready yet
  }

  try {
    const authStore = useAuthStore()
    if (authStore.token && !config.headers['X-User-Token']) {
      config.headers['X-User-Token'] = authStore.token
    }
  } catch {
    // Pinia not ready yet
  }

  return config
})

// Unified response error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Don't show toast for cancelled requests or explicit suppressions
    if (axios.isCancel(error)) return Promise.reject(error)

    const status = error.response?.status
    const data = error.response?.data

    // Server returned a business error with ok: false — treat as success so callers handle it
    if (data && typeof data === 'object' && 'ok' in data && !data.ok) {
      return Promise.reject(error)
    }

    // Network errors (no response)
    if (!error.response) {
      console.error('[API] Network error:', error.message || 'Connection failed')
    }
    // Server errors (5xx)
    else if (status >= 500) {
      console.error(`[API] Server error ${status}:`, data?.detail || data?.message || 'Internal server error')
    }
    // Client errors (4xx)
    else if (status === 401) {
      console.warn('[API] Unauthorized')
      try {
        const authStore = useAuthStore()
        // A per-request opt-out (used by invite-code login & public reader).
        const skipRedirect = (error.config as any)?._skipAuthRedirect === true
        const path = window.location.pathname
        // Never bounce away from the public reader (it must stay usable
        // anonymously even when a stale token 401s) or from auth/login flows.
        const publicPath =
          path.startsWith('/read') || path.startsWith('/login')
        authStore.setToken('')
        if (!skipRedirect && !publicPath) {
          window.location.href = '/login'
        }
      } catch {
        // Pinia not ready
      }
    } else if (status >= 400) {
      console.warn(`[API] Request error ${status}:`, data?.detail || data?.error || error.message)
    }

    return Promise.reject(error)
  },
)

export default client
