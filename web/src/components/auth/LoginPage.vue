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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    await authStore.loadConfig()
    if (!authStore.isAuthEnabled) {
      error.value = '当前未启用统一认证，请联系管理员。'
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
