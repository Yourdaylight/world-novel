<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand-icon">
        <svg width="48" height="48" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="50" cy="50" r="45" stroke="currentColor" stroke-width="2.5" opacity="0.25"/>
          <path d="M30 50 Q 35 25, 50 20 Q 65 25, 70 50 Q 65 75, 50 80 Q 35 75, 30 50Z" stroke="currentColor" stroke-width="2" opacity="0.6"/>
          <circle cx="50" cy="48" r="8" fill="currentColor" opacity="0.9"/>
          <line x1="50" y1="40" x2="50" y2="18" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
          <line x1="58" y1="52" x2="78" y2="60" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
        </svg>
      </div>
      <h1 class="brand-title">WorldNovel</h1>
      <p class="brand-subtitle">造物主的创世工坊</p>

      <div v-if="error" class="login-error" role="alert">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        {{ error }}
      </div>

      <!-- JWT mode: invite-code login / registration -->
      <template v-if="mode === 'jwt'">
        <input
          v-model="inviteCode"
          class="invite-input"
          type="text"
          placeholder="输入邀请码（注册 / 登录）"
          autocomplete="off"
          :disabled="submitting"
          @keyup.enter="loginWithCode"
        />
        <button
          class="btn-login"
          :disabled="submitting || !inviteCode.trim()"
          @click="loginWithCode"
        >
          <span v-if="submitting" class="btn-spinner"></span>
          <span v-else>注册 / 登录</span>
        </button>
        <p class="login-hint">
          输入邀请码即可注册并登录；注册后可免费阅读全站小说。
        </p>
      </template>

      <!-- Casdoor mode: redirect to SSO -->
      <template v-else-if="mode === 'casdoor'">
        <button
          class="btn-login"
          :disabled="loading || !authStore.isAuthEnabled"
          @click="authStore.login(true)"
        >
          <span v-if="loading" class="btn-spinner"></span>
          <span v-else-if="!authStore.isAuthEnabled">认证未配置</span>
          <span v-else>前往统一认证中心</span>
        </button>
        <p class="login-hint">登录即表示同意使用统一身份认证服务</p>
      </template>

      <!-- Auth disabled -->
      <template v-else>
        <p class="login-hint">当前环境未启用认证（auth_mode=disabled），无需登录。</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import client from '@/api/client'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const inviteCode = ref('')

const mode = computed(() => authStore.config?.mode || 'disabled')

function redirectAfterLogin() {
  // Reader came from a share page — go back and fire the conversion beacon there
  const fromShare = route.query.from_share
  if (fromShare) {
    router.replace({ path: `/read/${fromShare}`, query: { from_share: fromShare } })
    return
  }
  const redirect = route.query.redirect
  router.replace(typeof redirect === 'string' && redirect ? redirect : '/')
}

async function loginWithCode() {
  const code = inviteCode.value.trim()
  if (!code) return
  submitting.value = true
  error.value = ''
  try {
    const { data } = await client.post('/auth/login', { invite_code: code })
    authStore.setToken(data.access_token)
    await authStore.fetchMe()
    redirectAfterLogin()
  } catch (e: any) {
    const status = e.response?.status
    if (status === 401) {
      error.value = '邀请码无效或已被停用'
    } else if (status === 429) {
      error.value = '尝试过于频繁，请稍后再试'
    } else {
      error.value = e.response?.data?.detail || '登录失败，请重试'
    }
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    await authStore.loadConfig()
    if (mode.value === 'casdoor' && !authStore.isAuthEnabled) {
      error.value = '统一认证未配置，请联系管理员。'
    }
  } catch {
    error.value = '认证配置加载失败，请刷新页面重试。'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-gradient);
  padding: var(--sp-md);
}

.login-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  width: 100%;
  max-width: 400px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-deep);
  padding: var(--sp-xl);
  gap: var(--sp-md);
}

.brand-icon {
  color: var(--accent-ember);
  opacity: 0.9;
}

.brand-title {
  font-family: var(--font-display);
  font-size: var(--fs-2xl);
  font-weight: 400;
  margin: 0;
  letter-spacing: -0.02em;
}

.brand-subtitle {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin: 0 0 var(--sp-sm);
}

.login-error {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.25);
  color: var(--accent-cinnabar);
  border-radius: var(--radius-md);
  padding: var(--sp-sm) var(--sp-md);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
}

.btn-login {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 12px 24px;
  font-family: var(--font-ui);
  font-size: var(--fs-base);
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.02em;
  transition: all var(--duration-base) ease;
  box-shadow: 0 2px 10px rgba(217, 119, 6, 0.3);

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(217, 119, 6, 0.38);
    background: linear-gradient(135deg, #b45309, #92400e);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.login-hint {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  margin: 0;
  text-align: center;
}

.invite-input {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-void);
  color: var(--text-primary);
  font-family: var(--font-ui);
  font-size: var(--fs-base);
  outline: none;
  transition: border-color var(--duration-fast) ease;

  &:focus {
    border-color: var(--accent-ember);
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 480px) {
  .login-page {
    padding: var(--sp-sm);
  }

  .login-card {
    padding: var(--sp-lg);
    max-width: 100%;
  }
}
</style>
