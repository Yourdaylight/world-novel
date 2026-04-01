<template>
  <div class="overview-page" v-loading="loading">
    <!-- Hero CTA — most prominent element -->
    <HeroCTA :is-running="isRunning" :error-message="generationError" :novel-status="worldStatus.status" />

    <!-- Generation Error Alert -->
    <div class="generation-error-alert" v-if="generationError">
      <div class="error-alert-inner">
        <div class="error-alert-header">
          <span class="error-icon">✕</span>
          <span class="error-title">生成失败</span>
          <el-button text size="small" @click="generationError = ''">关闭</el-button>
        </div>
        <p class="error-detail">{{ generationError }}</p>
      </div>
    </div>

    <!-- Dashboard Grid: Info + Stats + Propositions -->
    <div class="dashboard-grid">
      <div class="grid-card">
        <NovelInfoCard />
      </div>

      <div class="grid-card">
        <WorldStats />
      </div>

      <div class="grid-card propositions-card" v-if="hasPropositions">
        <span class="card-title">终极命题</span>
        <div class="propositions-compact">
          <div class="prop-inline" v-if="propositions.what_is">
            <span class="prop-badge aurora">是什么</span>
            <span class="prop-value">{{ propositions.what_is }}</span>
          </div>
          <div class="prop-inline" v-if="propositions.where_from">
            <span class="prop-badge jade">从何来</span>
            <span class="prop-value">{{ propositions.where_from }}</span>
          </div>
          <div class="prop-inline" v-if="propositions.where_to">
            <span class="prop-badge ember">往何去</span>
            <span class="prop-value">{{ propositions.where_to }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Chapters -->
    <RecentChapters />

    <!-- Volume Tree -->
    <div style="margin-top: var(--sp-lg)">
      <VolumeTree />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, reactive, computed } from 'vue'
import { useRoute } from 'vue-router'
import NovelInfoCard from './NovelInfoCard.vue'
import VolumeTree from './VolumeTree.vue'
import WorldStats from './WorldStats.vue'
import HeroCTA from './HeroCTA.vue'
import RecentChapters from './RecentChapters.vue'
import { useWorldStore } from '@/stores/world'
import { useProgressStore } from '@/stores/progress'
import { fetchPropositions } from '@/api/novels'
import client from '@/api/client'
import { onWSEvent } from '@/composables/useWebSocket'

const route = useRoute()
const worldStore = useWorldStore()
const progressStore = useProgressStore()
const loading = ref(false)
const generationError = ref('')
const previousStatus = ref('idle')

const propositions = reactive({ what_is: '', where_from: '', where_to: '' })

interface WorldStatusData {
  status: string
  is_running: boolean
  chapters_completed: number
  chapters_total: number
  word_count: number
  progress: { phase: string; completed: number; total: number }
}
const worldStatus = reactive<WorldStatusData>({
  status: 'idle', is_running: false,
  chapters_completed: 0, chapters_total: 0, word_count: 0,
  progress: { phase: 'idle', completed: 0, total: 0 },
})

const hasPropositions = computed(() =>
  propositions.what_is || propositions.where_from || propositions.where_to
)

const isRunning = computed(() =>
  progressStore.phase !== 'idle' && progressStore.phase !== 'done' && progressStore.phase !== 'error' && !progressStore.paused
)

// ---- Polling ----
let pollTimer: ReturnType<typeof setInterval> | null = null

async function pollStatus() {
  const novelId = route.params.novelId as string
  if (!novelId) return
  try {
    const { data } = await client.get(`/worlds/${novelId}/status`)
    const wasGenerating = previousStatus.value === 'generating' || worldStatus.is_running
    Object.assign(worldStatus, data)
    if (data.progress) {
      progressStore.updateFromWS(data.progress)
    }
    if (wasGenerating && data.status === 'idle' && !data.is_running) {
      try {
        const { data: errData } = await client.get(`/worlds/${novelId}/generation-error`)
        if (errData.error) {
          generationError.value = errData.error
        }
      } catch { /* ignore */ }
    }
    previousStatus.value = data.status || 'idle'
  } catch { /* ignore */ }
}

const wsUnsubs: (() => void)[] = []

function setupWSListeners() {
  wsUnsubs.push(onWSEvent('phase_change', (event) => {
    worldStatus.progress.phase = event.phase
    if (event.phase !== 'idle' && event.phase !== 'done') {
      worldStatus.is_running = true
      worldStatus.status = 'generating'
    }
  }))

  wsUnsubs.push(onWSEvent('chapter_completed', (event) => {
    worldStatus.chapters_completed = event.chapter + 1
  }))

  wsUnsubs.push(onWSEvent('generation_started', () => {
    worldStatus.is_running = true
    worldStatus.status = 'generating'
    previousStatus.value = 'generating'
    generationError.value = ''
  }))

  wsUnsubs.push(onWSEvent('generation_finished', (event) => {
    worldStatus.is_running = false
    worldStatus.status = event.status || 'completed'
    worldStore.loadWorld()
    pollStatus()
  }))

  wsUnsubs.push(onWSEvent('generation_error', (event) => {
    worldStatus.is_running = false
    worldStatus.status = 'idle'
    generationError.value = event.error || '未知错误'
  }))
}

onMounted(async () => {
  loading.value = true
  const novelId = route.params.novelId as string
  await Promise.all([
    worldStore.loadWorld(),
    progressStore.loadProgress(),
    loadPropositions(novelId),
    pollStatus(),
  ])
  loading.value = false

  setupWSListeners()
  pollTimer = setInterval(pollStatus, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  wsUnsubs.forEach(fn => fn())
})

async function loadPropositions(novelId: string) {
  if (!novelId) return
  try {
    const data = await fetchPropositions(novelId)
    propositions.what_is = data.what_is || ''
    propositions.where_from = data.where_from || ''
    propositions.where_to = data.where_to || ''
  } catch { /* ignore */ }
}
</script>

<style scoped lang="scss">
.overview-page {
  min-height: 400px;
}

.generation-error-alert {
  margin-bottom: var(--sp-lg);

  .error-alert-inner {
    background: rgba(var(--accent-cinnabar-rgb, 220, 80, 60), 0.08);
    border: 1px solid var(--accent-cinnabar);
    border-radius: var(--radius-lg);
    padding: var(--sp-md) var(--sp-lg);
  }

  .error-alert-header {
    display: flex;
    align-items: center;
    gap: var(--sp-sm);
    margin-bottom: var(--sp-xs);
  }

  .error-icon {
    color: var(--accent-cinnabar);
    font-weight: 700;
    font-size: var(--fs-md);
  }

  .error-title {
    font-family: var(--font-ui);
    font-weight: 600;
    color: var(--accent-cinnabar);
    flex: 1;
  }

  .error-detail {
    font-family: var(--font-data);
    font-size: var(--fs-sm);
    color: var(--text-primary);
    margin: 0;
    word-break: break-all;
    line-height: 1.6;
  }
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
}

.grid-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--sp-md);
  min-width: 0;
}

.card-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  display: block;
  margin-bottom: var(--sp-sm);
}

.propositions-compact {
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}

.prop-inline {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-sm);
}

.prop-badge {
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 2px;

  &.aurora {
    color: var(--accent-aurora);
    background: rgba(166, 127, 212, 0.12);
  }
  &.jade {
    color: var(--accent-jade);
    background: rgba(78, 201, 148, 0.1);
  }
  &.ember {
    color: var(--accent-ember);
    background: var(--accent-ember-dim);
  }
}

.prop-value {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-primary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
