<template>
  <div class="dashboard-layout">
    <!-- Sidebar -->
    <aside class="dashboard-sidebar">
      <div class="sidebar-header">
        <div class="header-top">
          <button class="back-link" @click="router.push('/')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
            <span>首页</span>
          </button>
          <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换亮色' : '切换暗色'">
            <svg v-if="!isDark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          </button>
        </div>
        <h1 class="world-name">WorldNovel</h1>
        <div class="simulation-status" v-if="novelStore.activeNovelId">
          <span class="status-dot" :class="statusClass"></span>
          <span class="status-text">{{ statusLabel }}</span>
        </div>
        <div class="ws-status" v-if="!wsConnected">
          <span class="ws-dot"></span>
          <span class="ws-label">重连中...</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <a
          v-for="(tab, idx) in tabs"
          :key="tab.name"
          class="nav-item"
          :class="{ active: activeTab === tab.name }"
          @click="onTabChange(tab.name)"
          :style="{ animationDelay: `${idx * 30}ms` }"
        >
          <span class="nav-icon">{{ navIcons[tab.name] }}</span>
          <span class="nav-label">{{ tab.label }}</span>
        </a>
      </nav>

      <!-- Historian shortcut -->
      <div class="historian-shortcut" @click="onTabChange('historian')" v-if="novelStore.activeNovelId">
        <span class="historian-icon">&#9998;</span>
        与史官对话
      </div>

      <!-- Sidebar Footer -->
      <div class="sidebar-footer" v-if="novelStore.activeNovelId">
        <!-- Progress -->
        <div class="footer-progress">
          <div class="progress-label">
            <span>章节进度</span>
            <span class="progress-nums font-data">{{ progressStore.completed }}/{{ progressStore.total || '?' }}</span>
          </div>
          <div class="progress-track">
            <div
              class="progress-fill"
              :style="{ width: `${progressStore.percent}%`, background: progressBarGradient }"
            ></div>
          </div>
        </div>

        <!-- Mini event feed -->
        <div class="mini-events" v-if="recentEvents.length > 0">
          <div v-for="evt in recentEvents" :key="evt.time + evt.text" class="mini-event" @click="onTabChange('overview')">
            <span class="mini-time">{{ evt.time.substring(0, 5) }}</span>
            <span class="mini-text">{{ evt.text.substring(0, 28) }}</span>
          </div>
        </div>

        <!-- Control Buttons -->
        <div class="footer-controls">
          <button
            v-if="!isRunning && !progressStore.paused"
            class="ctrl-btn ctrl-primary"
            @click="handleStart"
            :disabled="isRunning"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
            开始生成
          </button>
          <button
            v-if="progressStore.paused"
            class="ctrl-btn ctrl-primary"
            @click="handleResume"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
            继续第{{ progressStore.completed + 1 }}章
          </button>
          <button
            v-if="isRunning"
            class="ctrl-btn ctrl-pause"
            @click="handlePause"
          >
            <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
            暂停
          </button>
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
import { ElMessage } from 'element-plus'
import { useWebSocket, onWSEvent } from '@/composables/useWebSocket'
import { useNovelStore } from '@/stores/novel'
import { useProgressStore } from '@/stores/progress'
import { useEventLogStore } from '@/stores/eventLog'
import { useTheme } from '@/composables/useTheme'
import client from '@/api/client'
import { startGeneration, resumeGeneration, pauseGeneration } from '@/api/novels'

const { isDark, toggleTheme } = useTheme()

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

const navIcons: Record<string, string> = {
  overview: '\u2302',
  'world-view': '\u2606',
  characters: '\u263A',
  timeline: '\u23F3',
  foreshadows: '\u2726',
  chapters: '\u25A0',
  tokens: '\u00B6',
  control: '\u2699',
}

const activeTab = ref(route.name as string || 'overview')

const isRunning = computed(() => progressStore.isRunning)

const progressBarColor = computed(() => {
  if (progressStore.paused) return '#6b7280'
  if (progressStore.phase === 'done') return '#059669'
  return '#d97706'
})

const progressBarGradient = computed(() => {
  const c = progressBarColor.value
  return `linear-gradient(90deg, ${c} 0%, ${c}cc 100%)`
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
  const novelId = novelStore.activeNovelId || route.params.novelId as string
  if (!novelId) return
  try {
    const res = await startGeneration(novelId)
    if (!res.ok) ElMessage.error(res.error || '启动失败')
    else progressStore.loadProgress()
  } catch (e) { /* ignore */ }
}

async function handleResume() {
  const novelId = novelStore.activeNovelId || route.params.novelId as string
  if (!novelId) return
  try {
    const res = await resumeGeneration(novelId)
    if (!res.ok) ElMessage.error(res.error || '继续失败')
    else progressStore.loadProgress()
  } catch (e) { /* ignore */ }
}

async function handlePause() {
  const novelId = novelStore.activeNovelId || route.params.novelId as string
  if (!novelId) return
  try {
    await pauseGeneration(novelId)
    progressStore.loadProgress()
  } catch (e) { /* ignore */ }
}

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

const { connect, disconnect, connected: wsConnected } = useWebSocket()
onMounted(() => {
  connect()
  novelStore.loadNovels()
  loadTokenStats()
})

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

/* ============================
   SIDEBAR — refined panel
   ============================ */
.dashboard-sidebar {
  width: 240px;
  min-width: 240px;
  height: 100vh;
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-default);
  overflow-y: auto;
}

.sidebar-header {
  padding: var(--sp-lg) var(--sp-md) var(--sp-md);
  border-bottom: 1px solid var(--border-default);
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-sm);
}

.theme-toggle {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-base) ease;

  &:hover {
    border-color: var(--accent-ember);
    color: var(--accent-ember);
    box-shadow: var(--glow-amber);
  }
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 500;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  transition: all var(--duration-base) ease;

  &:hover {
    color: var(--text-secondary);
    background: var(--bg-elevated);
  }
}

.world-name {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.simulation-status {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  margin-top: var(--sp-sm);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.ws-status {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  margin-top: var(--sp-xs);
  font-size: var(--fs-xs);
  color: var(--text-muted);

  .ws-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-cinnabar);
    animation: dot-blink 1.2s ease-in-out infinite;
  }

  .ws-label {
    color: var(--text-muted);
  }
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  &.idle     { background: var(--text-muted); }
  &.running  { background: var(--accent-ember); animation: status-pulse 2s ease-in-out infinite; }
  &.paused   { background: #60a5fa; }
  &.done     { background: var(--accent-jade); }
  &.error    { background: var(--accent-cinnabar); }
}

/* ============================
   NAV — clean list style
   ============================ */
.sidebar-nav {
  flex: 1;
  padding: var(--sp-sm) 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: 9px var(--sp-md);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 450;
  color: var(--text-secondary);
  cursor: pointer;
  text-decoration: none;
  border-left: 2.5px solid transparent;
  margin: 1px 0;
  transition: all var(--duration-fast) ease;
  position: relative;

  &:hover {
    color: var(--text-primary);
    background: var(--bg-elevated);
  }

  &.active {
    color: var(--accent-ember);
    border-left-color: var(--accent-ember);
    background: linear-gradient(90deg, var(--accent-ember-dim), transparent);
    font-weight: 550;
  }

  .nav-icon {
    font-size: 15px;
    opacity: 0.65;
    width: 20px;
    text-align: center;
    transition: opacity var(--duration-base) ease;
  }

  &.active .nav-icon,
  &:hover .nav-icon {
    opacity: 1;
  }

  .nav-label {
    white-space: nowrap;
  }
}

/* Historian shortcut */
.historian-shortcut {
  margin: var(--sp-xs) var(--sp-sm);
  padding: var(--sp-sm) var(--sp-md);
  background: linear-gradient(135deg, var(--bg-elevated), rgba(217,119,6,0.04));
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: center;
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  justify-content: center;
  transition: all var(--duration-base) ease;

  &:hover {
    color: var(--accent-ember);
    border-color: var(--accent-ember);
    border-style: solid;
    box-shadow: var(--glow-amber);
  }

  .historian-icon {
    font-size: 13px;
  }
}

/* ============================
   FOOTER — control area
   ============================ */
.sidebar-footer {
  border-top: 1px solid var(--border-default);
  padding: var(--sp-md);
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
  background: var(--bg-elevated);
}

.footer-progress {
  .progress-label {
    display: flex;
    justify-content: space-between;
    font-size: var(--fs-xs);
    color: var(--text-muted);
    margin-bottom: 6px;
    font-weight: 500;
  }

  .progress-nums {
    color: var(--text-secondary);
    font-weight: 600;
  }
}

.progress-track {
  height: 5px;
  background: var(--bg-void);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s var(--ease-out-expo);
}

.mini-events {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 80px;
  overflow-y: auto;
}

.mini-event {
  display: flex;
  gap: var(--sp-xs);
  padding: 3px 0;
  cursor: pointer;
  font-size: 11px;
  line-height: 1.45;
  border-radius: 3px;
  transition: background var(--duration-fast) ease;

  &:hover {
    background: var(--bg-surface);
  }
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
}

.ctrl-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px 12px;
  border: none;
  border-radius: var(--radius-md);
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-base) ease;
  letter-spacing: 0.01em;

  &.ctrl-primary {
    background: var(--accent-ember);
    color: var(--text-inverse);
    box-shadow: 0 2px 8px rgba(217, 119, 6, 0.25);

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 14px rgba(217, 119, 6, 0.35);
    }
  }

  &.ctrl-pause {
    background: var(--bg-surface);
    color: var(--text-secondary);
    border: 1px solid var(--border-default);

    &:hover {
      color: var(--text-primary);
      border-color: var(--text-muted);
    }
  }
}

.footer-tokens {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-xs);
  color: var(--text-muted);
  padding-top: var(--sp-xs);
  border-top: 1px solid var(--border-default);
  margin-top: 2px;

  .token-count {
    color: var(--accent-ember);
    font-weight: 650;
    font-size: var(--fs-sm);
  }

  .token-label {
    color: var(--text-muted);
  }
}

.dashboard-main {
  flex: 1;
  min-width: 0;
  background: var(--bg-void);
  position: relative;
}

.dashboard-main::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--bg-noise);
  pointer-events: none;
  z-index: 0;
  opacity: 0.5;
}

.dashboard-content {
  max-width: 1100px;
  padding: var(--sp-xl);
  min-height: 100vh;
  position: relative;
  z-index: 1;
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.35; transform: scale(0.85); }
}
@keyframes dot-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.2; }
}
</style>
