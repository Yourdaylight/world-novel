<template>
  <div class="dashboard-layout">
    <!-- Sidebar -->
    <aside class="dashboard-sidebar">
      <div class="sidebar-header">
        <button class="back-link" @click="router.push('/')">← 首页</button>
        <h1 class="world-name">WorldEngine</h1>
        <div class="simulation-status" v-if="novelStore.activeNovelId">
          <span class="status-dot" :class="statusClass">●</span>
          <span class="status-text">{{ statusLabel }}</span>
        </div>
        <div class="ws-status" v-if="!wsConnected">
          <span class="ws-dot">●</span>
          <span class="ws-label">重连中...</span>
        </div>
      </div>
      <nav class="sidebar-nav">
        <a
          v-for="tab in tabs"
          :key="tab.name"
          class="nav-item"
          :class="{ active: activeTab === tab.name }"
          @click="onTabChange(tab.name)"
        >
          <span class="nav-label">{{ tab.label }}</span>
        </a>
      </nav>

      <!-- Historian shortcut -->
      <div class="historian-shortcut" @click="onTabChange('historian')" v-if="novelStore.activeNovelId">
        与史官对话
      </div>

      <!-- Sidebar Footer: Generation Control -->
      <div class="sidebar-footer" v-if="novelStore.activeNovelId">
        <!-- Progress -->
        <div class="footer-progress">
          <div class="progress-label">
            <span>章节进度</span>
            <span class="progress-nums font-data">{{ progressStore.completed }}/{{ progressStore.total || '?' }}</span>
          </div>
          <el-progress
            :percentage="progressStore.percent"
            :stroke-width="6"
            :show-text="false"
            :color="progressBarColor"
          />
        </div>

        <!-- Mini event feed -->
        <div class="mini-events" v-if="recentEvents.length > 0">
          <div v-for="evt in recentEvents" :key="evt.time + evt.text" class="mini-event" @click="onTabChange('overview')">
            <span class="mini-time">{{ evt.time.substring(0, 5) }}</span>
            <span class="mini-text">{{ evt.text.substring(0, 30) }}</span>
          </div>
        </div>

        <!-- Control Buttons -->
        <div class="footer-controls">
          <el-button
            v-if="!isRunning && !progressStore.paused"
            type="primary"
            size="small"
            @click="handleStart"
            :disabled="isRunning"
          >
            ▶ 开始生成
          </el-button>
          <el-button
            v-if="progressStore.paused"
            type="primary"
            size="small"
            @click="handleResume"
          >
            ▶ 继续生成第{{ progressStore.completed + 1 }}章
          </el-button>
          <el-button
            v-if="isRunning"
            type="warning"
            size="small"
            @click="handlePause"
          >
            ⏸ 暂停
          </el-button>
        </div>

        <!-- Token Counter -->
        <div class="footer-tokens" v-if="tokenTotal > 0">
          <span class="token-count font-data">{{ formatTokens(tokenTotal) }}</span>
          <span class="token-label">tokens</span>
        </div>
      </div>
    </aside>
    <!-- Main content -->
    <main class="dashboard-main">
      <div class="dashboard-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useWebSocket, onWSEvent } from '@/composables/useWebSocket'
import { useNovelStore } from '@/stores/novel'
import { useProgressStore } from '@/stores/progress'
import { useEventLogStore } from '@/stores/eventLog'
import client from '@/api/client'

const router = useRouter()
const route = useRoute()
const novelStore = useNovelStore()
const progressStore = useProgressStore()
const eventLogStore = useEventLogStore()
const tokenTotal = ref(0)

const tabs = [
  { name: 'overview',    label: '概览' },
  { name: 'world-view',  label: '世界观' },
  { name: 'characters',  label: '角色' },
  { name: 'timeline',    label: '大纲与时间线' },
  { name: 'foreshadows', label: '伏笔' },
  { name: 'chapters',    label: '章节' },
  { name: 'tokens',      label: 'Token 统计' },
  { name: 'control',     label: '控制台' },
]

const activeTab = ref(route.name as string || 'overview')

const isRunning = computed(() => {
  return progressStore.phase !== 'idle' && progressStore.phase !== 'done' && progressStore.phase !== 'error' && !progressStore.paused
})

const progressBarColor = computed(() => {
  if (progressStore.paused) return '#64748b'
  if (progressStore.phase === 'done') return '#4ec994'
  return '#d4793a'
})

const statusClass = computed(() => {
  if (progressStore.phase === 'error') return 'error'
  if (progressStore.phase === 'done') return 'done'
  if (progressStore.paused) return 'paused'
  if (isRunning.value) return 'running'
  return 'idle'
})

const statusLabel = computed(() => {
  if (progressStore.phase === 'error') return '出错'
  if (progressStore.phase === 'done') return `已完成 · ${progressStore.completed}/${progressStore.total}章`
  if (progressStore.paused) return `已暂停 · ${progressStore.completed}/${progressStore.total}章`
  if (isRunning.value) return `生成中 · ${progressStore.completed}/${progressStore.total}章`
  return '待命'
})

const recentEvents = computed(() => {
  return eventLogStore.entries.slice(-5).reverse()
})

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

async function loadTokenStats() {
  try {
    const res = await client.get('/token-stats')
    tokenTotal.value = res.data.total?.total_tokens || 0
  } catch { /* ignore */ }
}

async function handleStart() {
  try {
    await client.post('/start-generation')
  } catch { /* ignore */ }
}

async function handleResume() {
  try {
    await client.post('/resume-generation')
  } catch { /* ignore */ }
}

async function handlePause() {
  try {
    await client.post('/pause-generation')
  } catch { /* ignore */ }
}

// Switch active novel based on route param
watch(
  () => route.params.novelId as string,
  (novelId) => {
    if (novelId && novelId !== novelStore.activeNovelId) {
      novelStore.switchNovel(novelId)
    }
  },
  { immediate: true }
)

watch(() => route.name, (name) => {
  if (name) activeTab.value = name as string
})

function onTabChange(name: string | number) {
  const novelId = route.params.novelId
  router.push({ name: name as string, params: { novelId: novelId as string } })
}

// WebSocket connection
const { connect, disconnect, connected: wsConnected } = useWebSocket()
onMounted(() => {
  connect()
  novelStore.loadNovels()
  loadTokenStats()
})

// Auto-refresh token count on WS event
const unsubToken = onWSEvent('token_update', () => {
  loadTokenStats()
})

onUnmounted(() => {
  disconnect()
  unsubToken()
})
</script>

<style scoped lang="scss">
.dashboard-layout {
  min-height: 100vh;
  display: flex;
}

.dashboard-sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-rule);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

.sidebar-header {
  padding: var(--sp-lg) var(--sp-md);
  border-bottom: 1px solid var(--border-rule);
}

.back-link {
  background: none;
  border: none;
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  cursor: pointer;
  padding: 0;
  margin-bottom: var(--sp-sm);
  display: block;

  &:hover {
    color: var(--text-secondary);
  }
}

.world-name {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.2;
}

.simulation-status {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  margin-top: var(--sp-sm);
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.ws-status {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  margin-top: var(--sp-xs);
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);

  .ws-dot {
    font-size: 8px;
    color: var(--accent-cinnabar);
  }

  .ws-label {
    color: var(--text-muted);
  }
}

.status-dot {
  font-size: 8px;
  &.idle { color: var(--text-muted); }
  &.running { color: var(--accent-ember); animation: status-pulse 2s ease-in-out infinite; }
  &.paused { color: var(--accent-blue, #58a6ff); }
  &.done { color: var(--accent-jade); }
  &.error { color: var(--accent-cinnabar); }
}

.sidebar-nav {
  flex: 1;
  padding: var(--sp-sm) 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-sm) var(--sp-md);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  cursor: pointer;
  text-decoration: none;
  border-left: 2px solid transparent;
  transition: none;

  &:hover {
    color: var(--text-primary);
    background: var(--bg-elevated);
  }

  &.active {
    color: var(--accent-ember);
    border-left-color: var(--accent-ember);
    background: var(--accent-ember-dim);
  }

  .nav-label {
    white-space: nowrap;
  }
}

.historian-shortcut {
  padding: var(--sp-sm) var(--sp-md);
  margin: var(--sp-xs) var(--sp-sm);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  cursor: pointer;
  text-align: center;

  &:hover {
    color: var(--text-primary);
    border-color: var(--accent-ember);
  }
}

/* Sidebar Footer — Generation Control */
.sidebar-footer {
  border-top: 1px solid var(--border-rule);
  padding: var(--sp-md);
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}

.footer-progress {
  .progress-label {
    display: flex;
    justify-content: space-between;
    font-size: var(--fs-xs);
    color: var(--text-muted);
    margin-bottom: var(--sp-xs);
  }

  .progress-nums {
    color: var(--text-secondary);
    font-size: var(--fs-xs);
  }
}

.mini-events {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: var(--sp-xs);
}

.mini-event {
  display: flex;
  gap: var(--sp-xs);
  padding: 2px 0;
  cursor: pointer;
  font-size: 10px;
  line-height: 1.4;

  &:hover .mini-text { color: var(--text-secondary); }
}

.mini-time {
  color: var(--text-muted);
  font-family: var(--font-data);
  flex-shrink: 0;
}

.mini-text {
  color: var(--text-muted);
  font-family: var(--font-ui);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.footer-controls {
  display: flex;
  gap: var(--sp-xs);

  .el-button {
    flex: 1;
    font-size: var(--fs-xs);
  }
}

.footer-tokens {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  padding-top: var(--sp-xs);

  .token-icon {
    font-size: 12px;
  }

  .token-count {
    color: var(--accent-ember);
    font-weight: 600;
  }

  .token-label {
    color: var(--text-muted);
  }
}

.dashboard-main {
  flex: 1;
  min-width: 0;
  background: var(--bg-void);
}

.dashboard-content {
  max-width: 1100px;
  padding: var(--sp-xl);
  min-height: 100vh;
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
