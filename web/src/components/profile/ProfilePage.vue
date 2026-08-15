<template>
  <div class="profile-page">
    <div class="content-wrap">
      <header class="profile-header">
        <button class="back-btn" @click="goBack">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          返回
        </button>
        <h1 class="profile-title">个人中心</h1>
      </header>

      <div v-loading="loading" class="profile-grid">
        <section class="profile-card user-card">
          <div class="avatar-wrap">
            <img v-if="avatarUrl" :src="avatarUrl" alt="avatar" class="avatar-img" />
            <div v-else class="avatar-placeholder">
              {{ initials }}
            </div>
          </div>
          <h2 class="user-display-name">{{ displayName }}</h2>
          <p class="user-username">@{{ identity?.username || '-' }}</p>
          <div class="user-badges">
            <el-tag v-if="identity?.is_admin" type="warning" effect="dark" size="small">管理员</el-tag>
            <el-tag v-else type="info" size="small">普通用户</el-tag>
          </div>
          <div class="user-actions">
            <el-button type="danger" plain @click="handleLogout">退出登录</el-button>
          </div>
        </section>

        <section class="profile-card details-card">
          <h3 class="card-heading">账户详情</h3>
          <dl class="details-list">
            <div class="details-row">
              <dt>显示名</dt>
              <dd>{{ identity?.display_name || '-' }}</dd>
            </div>
            <div class="details-row">
              <dt>用户名</dt>
              <dd>{{ identity?.username || '-' }}</dd>
            </div>
            <div class="details-row">
              <dt>邮箱</dt>
              <dd>{{ identity?.email || '-' }}</dd>
            </div>
            <div class="details-row">
              <dt>组织</dt>
              <dd>{{ identity?.organization || '-' }}</dd>
            </div>
            <div class="details-row">
              <dt>用户 ID</dt>
              <dd class="mono">{{ identity?.sub || '-' }}</dd>
            </div>
          </dl>

          <div class="details-actions">
            <el-button type="danger" @click="handleLogout">退出登录</el-button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)

const identity = computed(() => authStore.identity)
const displayName = computed(() => authStore.displayName)
const avatarUrl = computed(() => identity.value?.avatar)

const initials = computed(() => {
  const name = identity.value?.display_name || identity.value?.username || '用户'
  return name.slice(0, 2).toUpperCase()
})

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push({ name: 'home' })
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    authStore.logout()
  } catch {
    // user cancelled
  }
}

onMounted(async () => {
  loading.value = true
  try {
    if (!authStore.config) {
      await authStore.init()
    } else {
      await authStore.loadIdentity()
    }
    if (authStore.isAuthEnabled && !authStore.isAuthenticated) {
      ElMessage.warning('请先登录')
      router.replace({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.profile-page {
  min-height: 100vh;
  padding: var(--sp-lg) 0;
  background: var(--bg-void);
  color: var(--text-primary);
}

.content-wrap {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 var(--sp-lg);
}

.profile-header {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  margin-bottom: var(--sp-xl);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-xs);
  padding: var(--sp-xs) var(--sp-sm);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition: all var(--duration-base) ease;

  &:hover {
    border-color: var(--accent-ember);
    color: var(--accent-ember);
  }
}

.profile-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 600;
  margin: 0;
}

.profile-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: var(--sp-lg);
  align-items: start;
}

.profile-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--sp-xl);
}

.user-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.avatar-wrap {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  overflow: hidden;
  margin-bottom: var(--sp-md);
  background: var(--bg-elevated);
  border: 2px solid var(--border-default);
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--fs-xl);
  font-weight: 600;
  color: var(--text-inverse);
  background: linear-gradient(135deg, var(--accent-ember), #b45309);
}

.user-display-name {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 600;
  margin: 0 0 var(--sp-xs);
}

.user-username {
  font-size: var(--fs-sm);
  color: var(--text-muted);
  margin: 0 0 var(--sp-md);
}

.user-badges {
  margin-bottom: var(--sp-lg);
}

.user-actions {
  width: 100%;
  :deep(.el-button) {
    width: 100%;
  }
}

.card-heading {
  font-family: var(--font-ui);
  font-size: var(--fs-md);
  font-weight: 600;
  margin: 0 0 var(--sp-lg);
  padding-bottom: var(--sp-sm);
  border-bottom: 1px solid var(--border-muted);
}

.details-list {
  margin: 0;
}

.details-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-muted);

  &:last-child {
    border-bottom: none;
  }

  dt {
    font-size: var(--fs-sm);
    color: var(--text-muted);
    min-width: 80px;
  }

  dd {
    margin: 0;
    font-size: var(--fs-base);
    color: var(--text-primary);
    text-align: right;
    word-break: break-all;

    &.mono {
      font-family: var(--font-data);
      font-size: var(--fs-xs);
      color: var(--text-secondary);
    }
  }
}

.details-actions {
  margin-top: var(--sp-lg);
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }

  .profile-page {
    padding: var(--sp-md) 0;
  }

  .content-wrap {
    padding: 0 var(--sp-md);
  }
}
</style>
