import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import client from '@/api/client'

const TOKEN_KEY = 'casdoor_auth_token'
const FORCE_RELOGIN_KEY = 'force_relogin'

export interface AuthIdentity {
  sub: string
  username: string
  display_name: string
  email: string
  organization: string
  avatar?: string
  is_admin?: boolean
}

function firstString(value: unknown): string | undefined {
  if (typeof value === 'string' && value.trim() !== '') {
    return value
  }
  return undefined
}

function normalizeIdentity(raw: unknown): AuthIdentity | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const src = raw as Record<string, unknown>
  const username = firstString(src.username)
  if (!username) {
    return null
  }
  return {
    sub: firstString(src.sub) || username,
    username,
    display_name: firstString(src.display_name ?? src.displayName) || username,
    email: firstString(src.email) || '',
    organization: firstString(src.organization) || '',
    avatar: firstString(src.avatar ?? src.picture),
    is_admin: src.is_admin === true || src.isAdmin === true,
  }
}

export interface AuthConfig {
  mode: string
  sidecar_enabled: boolean
  login_url?: string
  oauth_login_url?: string
  logout_url?: string
  organization?: string
  application?: string
}

export const useAuthStore = defineStore('auth', () => {
  const config = ref<AuthConfig | null>(null)
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const identity = ref<AuthIdentity | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const isAuthEnabled = computed(() => config.value?.sidecar_enabled === true)
  const displayName = computed(() => {
    return identity.value?.display_name || identity.value?.username || '用户'
  })

  async function loadConfig(): Promise<AuthConfig> {
    try {
      const { data } = await client.get('/auth/config')
      config.value = data
      return data
    } catch (e) {
      console.error('[Auth] Failed to load auth config:', e)
      config.value = { mode: 'disabled', sidecar_enabled: false }
      return config.value
    }
  }

  function setToken(newToken: string) {
    token.value = newToken
    if (newToken) {
      localStorage.setItem(TOKEN_KEY, newToken)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  }

  function consumeCallbackToken() {
    // Sidecar bridge page may set token via localStorage; also check URL query.
    const url = new URL(window.location.href)
    const urlToken = url.searchParams.get('token')
    if (urlToken) {
      setToken(urlToken)
      // Clean token from URL without reload
      url.searchParams.delete('token')
      window.history.replaceState({}, '', url.toString())
    }
  }

  async function fetchMe(): Promise<AuthIdentity | null> {
    if (!token.value) {
      identity.value = null
      return null
    }
    try {
      const { data } = await client.get('/auth/me', {
        headers: { 'X-User-Token': token.value },
      })
      if (data?.ok && data.user) {
        identity.value = normalizeIdentity(data.user)
        if (data.token && data.token !== token.value) {
          setToken(data.token)
        }
        return identity.value
      }
    } catch (e: any) {
      if (e.response?.status === 401) {
        setToken('')
      }
      console.error('[Auth] fetchMe failed:', e)
    }
    identity.value = null
    return null
  }

  async function loadIdentity(): Promise<AuthIdentity | null> {
    return fetchMe()
  }

  function login(prompt = false) {
    if (!config.value?.login_url) {
      console.error('[Auth] Login URL not available')
      return
    }
    let url = config.value.oauth_login_url || config.value.login_url
    if (prompt || localStorage.getItem(FORCE_RELOGIN_KEY)) {
      const sep = url.includes('?') ? '&' : '?'
      url += `${sep}prompt=login`
      localStorage.removeItem(FORCE_RELOGIN_KEY)
    }
    window.location.href = url
  }

  async function logout() {
    const currentToken = token.value
    setToken('')
    identity.value = null
    localStorage.setItem(FORCE_RELOGIN_KEY, '1')

    if (currentToken && config.value?.logout_url) {
      try {
        await client.post(config.value.logout_url, {}, {
          headers: { 'X-User-Token': currentToken },
        })
      } catch (e) {
        console.warn('[Auth] Logout request failed:', e)
      }
    }

    // Redirect to home; sidecar logout page handles Casdoor session cleanup if needed.
    window.location.href = '/'
  }

  async function init() {
    await loadConfig()
    consumeCallbackToken()
    if (token.value) {
      await fetchMe()
    }
  }

  return {
    config,
    token,
    identity,
    loading,
    isAuthenticated,
    isAuthEnabled,
    displayName,
    loadConfig,
    setToken,
    fetchMe,
    loadIdentity,
    login,
    logout,
    init,
  }
})
