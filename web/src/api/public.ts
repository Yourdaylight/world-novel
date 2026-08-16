// Bare axios instance for the public reader (/read/:shareId).
// Deliberately does NOT use api/client.ts: that client injects the active
// novel_id, bounces 401s to the workbench login page, and attaches the
// author token — none of which apply to anonymous public reading.
import axios from 'axios'

const READER_TOKEN_KEY = 'worldnovel_reader_token'

export const publicClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Attach a reader-identity token if the visitor registered on a reader page.
publicClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(READER_TOKEN_KEY)
  if (token) {
    config.headers['X-User-Token'] = token
  }
  return config
})

// 401 from auth endpoints → surface to caller; never force-redirect.
publicClient.interceptors.response.use(
  (r) => r,
  (error) => Promise.reject(error),
)

export function readerToken(): string {
  return localStorage.getItem(READER_TOKEN_KEY) || ''
}

export function setReaderToken(token: string) {
  if (token) localStorage.setItem(READER_TOKEN_KEY, token)
  else localStorage.removeItem(READER_TOKEN_KEY)
}

export { READER_TOKEN_KEY }
