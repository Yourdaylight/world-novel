<template>
  <div class="overview-page" v-loading="loading">
    <!-- Generation Action Panel -->
    <div class="generation-panel ledger-rule">
      <div class="gen-panel-inner">
        <div class="gen-info">
          <h2 v-if="isIdle && !worldStatus.is_running">开始生成</h2>
          <h2 v-else-if="worldStatus.is_running || worldStatus.status === 'generating'">生成进行中</h2>
          <h2 v-else-if="worldStatus.status === 'paused'">生成已暂停</h2>
          <h2 v-else-if="worldStatus.status === 'completed'">生成完成</h2>
          <h2 v-else>开始生成</h2>

          <p v-if="isIdle && !worldStatus.is_running">
            基于三个终极命题，AI 将自动生成世界观、角色、时间线、伏笔和完整章节
          </p>
          <p v-else-if="worldStatus.is_running || worldStatus.status === 'generating'">
            {{ currentPhaseLabel }}
            <span v-if="worldStatus.chapters_completed > 0">
              — {{ worldStatus.chapters_completed }}/{{ worldStatus.chapters_total }} 章
            </span>
          </p>
          <p v-else-if="worldStatus.status === 'completed'">
            共 {{ worldStatus.chapters_completed }} 章 · {{ wordCountDisplay }} 字
          </p>
        </div>
        <div class="gen-actions">
          <el-select v-if="canStart" v-model="runMode" size="default" style="width: 130px; margin-right: 12px">
            <el-option label="全自动" value="full" />
            <el-option label="逐章暂停" value="chapter_by_chapter" />
          </el-select>
          <el-button
            v-if="canStartFresh"
            type="success"
            size="large"
            :loading="starting"
            @click="onStartGeneration"
          >
            开始生成
          </el-button>
          <el-button
            v-if="canResume"
            type="primary"
            size="large"
            :loading="starting"
            @click="onResumeGeneration"
          >
            ▶ 继续生成第{{ worldStatus.chapters_completed + 1 }}章
          </el-button>
          <el-button
            v-if="worldStatus.is_running"
            type="warning"
            size="large"
            :loading="pausing"
            @click="onPause"
          >
            ⏸ 暂停
          </el-button>
          <div v-if="worldStatus.is_running" class="running-indicator">
            <el-progress
              v-if="worldStatus.chapters_total > 0 && worldStatus.chapters_completed > 0"
              :percentage="Math.round(worldStatus.chapters_completed / worldStatus.chapters_total * 100)"
              :stroke-width="14"
              style="width: 180px"
            />
            <span class="running-dot">●</span> 运行中
          </div>
        </div>
      </div>
    </div>

    <!-- Real-time Event Log -->
    <div class="event-log-panel ledger-rule" v-if="eventLogStore.entries.length > 0">
      <div class="event-log-header">
        <span class="section-label">实时事件日志</span>
        <el-button text size="small" @click="eventLogStore.clear()">清空</el-button>
      </div>
      <div class="event-log-body" ref="logContainer">
        <div
          v-for="(evt, i) in eventLogStore.entries"
          :key="i"
          :class="['event-item', `event-${evt.type}`]"
        >
          <span class="event-time">{{ evt.time }}</span>
          <span class="event-text">{{ evt.text }}</span>
        </div>
      </div>
    </div>

    <!-- Chapter Review Panel -->
    <div class="chapter-review-panel ledger-rule" v-if="showChapterReview">
      <div class="review-header">
        <span class="section-label">章节审阅</span>
        <el-tag type="warning" effect="plain" size="small">逐章暂停中</el-tag>
      </div>
      <div class="review-body">
        <div class="review-summary" v-if="lastChapterSummary">
          <span class="review-chapter-label">第{{ worldStatus.chapters_completed }}章已完成</span>
          <p class="review-chapter-summary">{{ lastChapterSummary }}</p>
        </div>
        <div class="review-guidance">
          <label class="guidance-label">给下一章的导演建议（可留空）</label>
          <el-input
            v-model="directorGuidance"
            type="textarea"
            :rows="3"
            placeholder="例如：下一章希望增加主角与反派的直接对抗、加快节奏、揭示某个秘密..."
            resize="vertical"
          />
        </div>
        <div class="review-actions">
          <el-button type="success" size="large" :loading="starting" @click="onResumeWithGuidance">
            ✅ 继续生成第{{ worldStatus.chapters_completed + 1 }}章
          </el-button>
          <el-button type="info" size="large" @click="onStayPaused">
            ⏸ 暂停，稍后继续
          </el-button>
        </div>
      </div>
    </div>

    <!-- Live Writing Stream -->
    <LiveWritingPanel />

    <!-- Dashboard Grid: Propositions + Info + Stats -->
    <div class="dashboard-grid">
      <!-- Propositions — compact inline -->
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

      <!-- Novel Info — compact -->
      <div class="grid-card">
        <NovelInfoCard />
      </div>

      <!-- World Stats — compact -->
      <div class="grid-card">
        <WorldStats />
      </div>
    </div>

    <!-- Volume Tree -->
    <div style="margin-top: var(--sp-lg)">
      <VolumeTree />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, reactive, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import NovelInfoCard from './NovelInfoCard.vue'
import VolumeTree from './VolumeTree.vue'
import WorldStats from './WorldStats.vue'
import LiveWritingPanel from '@/components/chapters/LiveWritingPanel.vue'
import { useWorldStore } from '@/stores/world'
import { useProgressStore } from '@/stores/progress'
import { fetchPropositions, startGeneration, resumeGeneration, pauseGeneration } from '@/api/novels'
import client from '@/api/client'
import { useLiveWritingStore } from '@/stores/liveWriting'
import { useEventLogStore } from '@/stores/eventLog'

const route = useRoute()
const worldStore = useWorldStore()
const progressStore = useProgressStore()
const liveWritingStore = useLiveWritingStore()
const eventLogStore = useEventLogStore()
const loading = ref(false)
const starting = ref(false)
const pausing = ref(false)
const runMode = ref('full')
const logContainer = ref<HTMLElement | null>(null)
const directorGuidance = ref('')
const lastChapterSummary = ref('')

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

const isIdle = computed(() =>
  worldStatus.status === 'idle' && !worldStatus.is_running
)
const canStart = computed(() =>
  (worldStatus.status === 'idle' || worldStatus.status === 'paused') && !worldStatus.is_running
)
const canStartFresh = computed(() =>
  worldStatus.status === 'idle' && !worldStatus.is_running && worldStatus.chapters_completed === 0
)
const canResume = computed(() =>
  (worldStatus.status === 'paused' || (worldStatus.status === 'idle' && worldStatus.chapters_completed > 0))
  && !worldStatus.is_running
)

const showChapterReview = computed(() =>
  worldStatus.status === 'paused' && worldStatus.chapters_completed > 0 && !worldStatus.is_running
)

const phaseLabels: Record<string, string> = {
  directing: '导演规划 — 分析命题、设计冲突弧线',
  world_building: '构建世界 — 生成地理、势力、魔法体系',
  foreshadow_planning: '伏笔网络 — 规划植入点和回收时机',
  simulating: '模拟角色场景',
  writing: '撰写章节',
  reviewing: '审校伏笔',
  god_deliberation: '命运裁决',
}
const currentPhaseLabel = computed(() =>
  phaseLabels[worldStatus.progress.phase] || worldStatus.progress.phase || '处理中...'
)

const wordCountDisplay = computed(() => {
  const wc = worldStatus.word_count
  return wc > 10000 ? `${(wc / 10000).toFixed(1)}万` : wc.toLocaleString()
})

// ---- Polling ----
let pollTimer: ReturnType<typeof setInterval> | null = null

async function pollStatus() {
  const novelId = route.params.novelId as string
  if (!novelId) return
  try {
    const { data } = await client.get(`/worlds/${novelId}/status`)
    Object.assign(worldStatus, data)
    if (data.progress) {
      progressStore.updateFromWS(data.progress)
    }
  } catch { /* ignore */ }
}

function addEvent(text: string, type: string = 'info') {
  eventLogStore.addEntry(text, type)
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

function setupWSListener() {
  liveWritingStore.$onAction(({ name, args }) => {
    if (name === 'handleEvent') {
      const event = args[0]
      const t = event.type
      if (t === 'phase_change') {
        worldStatus.progress.phase = event.phase
        if (event.phase !== 'idle' && event.phase !== 'done') {
          worldStatus.is_running = true
          worldStatus.status = 'generating'
        }
      } else if (t === 'chapter_completed') {
        worldStatus.chapters_completed = event.chapter + 1
        lastChapterSummary.value = event.title ? `${event.title} (${event.word_count}字)` : ''
      } else if (t === 'generation_started') {
        worldStatus.is_running = true
        worldStatus.status = 'generating'
      } else if (t === 'generation_finished') {
        worldStatus.is_running = false
        worldStatus.status = event.status || 'completed'
        worldStore.loadWorld()
        pollStatus()
      } else if (t === 'generation_error') {
        worldStatus.is_running = false
        worldStatus.status = 'idle'
      }
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })
    }
  })
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

  setupWSListener()

  pollTimer = setInterval(pollStatus, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
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

async function onStartGeneration() {
  const novelId = route.params.novelId as string
  if (!novelId) return

  starting.value = true
  try {
    const res = await startGeneration(novelId, runMode.value)
    if (res.ok) {
      ElMessage.success('生成已启动')
      addEvent('生成请求已发送，等待响应...', 'start')
      worldStatus.is_running = true
      worldStatus.status = 'generating'
    } else {
      ElMessage.error(res.error || '启动失败')
      addEvent(`启动失败: ${res.error}`, 'error')
    }
  } finally {
    starting.value = false
  }
}

async function onResumeGeneration() {
  const novelId = route.params.novelId as string
  if (!novelId) return

  starting.value = true
  try {
    const res = await resumeGeneration(novelId, runMode.value)
    if (res.ok) {
      ElMessage.success('继续生成已启动！新设定将自动融入后续章节')
      addEvent(`从第${worldStatus.chapters_completed + 1}章继续生成（新设定已融入）`, 'start')
      worldStatus.is_running = true
      worldStatus.status = 'generating'
    } else {
      ElMessage.error(res.error || '恢复失败')
      addEvent(`恢复失败: ${res.error}`, 'error')
    }
  } finally {
    starting.value = false
  }
}

async function onPause() {
  const novelId = route.params.novelId as string
  if (!novelId) return

  pausing.value = true
  try {
    const res = await pauseGeneration(novelId)
    if (res.ok) {
      ElMessage.success('已暂停，当前章节完成后停止')
      addEvent('生成已暂停', 'phase')
      worldStatus.is_running = false
      worldStatus.status = 'paused'
    }
  } finally {
    pausing.value = false
  }
}

async function onResumeWithGuidance() {
  const novelId = route.params.novelId as string
  if (!novelId) return

  starting.value = true
  try {
    const guidance = directorGuidance.value.trim() || undefined
    const res = await resumeGeneration(novelId, 'chapter_by_chapter', guidance)
    if (res.ok) {
      ElMessage.success(guidance ? '继续生成，导演建议已注入！' : '继续生成下一章！')
      addEvent(`从第${worldStatus.chapters_completed + 1}章继续生成${guidance ? '（已注入导演建议）' : ''}`, 'start')
      worldStatus.is_running = true
      worldStatus.status = 'generating'
      directorGuidance.value = ''
      lastChapterSummary.value = ''
    } else {
      ElMessage.error(res.error || '恢复失败')
    }
  } finally {
    starting.value = false
  }
}

function onStayPaused() {
  ElMessage.info('保持暂停状态，随时可以继续')
}
</script>

<style scoped lang="scss">
.overview-page {
  min-height: 400px;
}

.generation-panel {
  margin-bottom: var(--sp-lg);

  .gen-panel-inner {
    background: var(--accent-ember-dim);
    border: 1px solid var(--border-rule);
    border-radius: 6px;
    padding: var(--sp-lg) var(--sp-xl);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--sp-xl);
  }

  .gen-info {
    flex: 1;
    h2 {
      font-family: var(--font-display);
      font-size: var(--fs-lg);
      font-weight: 400;
      color: var(--text-primary);
      margin: 0 0 var(--sp-xs) 0;
    }
    p {
      color: var(--text-secondary);
      font-family: var(--font-ui);
      font-size: var(--fs-sm);
      margin: 0;
    }
  }

  .gen-actions {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }

  .running-indicator {
    display: flex;
    align-items: center;
    gap: var(--sp-sm);
    color: var(--accent-phosphor);
    font-family: var(--font-data);
    font-size: var(--fs-sm);
    font-weight: 500;

    .running-dot {
      animation: blink 1.2s infinite;
    }
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.event-log-panel {
  margin-bottom: var(--sp-lg);

  .event-log-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--sp-sm);
  }

  .event-log-body {
    max-height: 240px;
    overflow-y: auto;
    padding: 0;
    font-family: var(--font-data);
    font-size: var(--fs-xs);
  }

  .event-item {
    padding: var(--sp-xs) 0;
    display: flex;
    gap: var(--sp-sm);
    line-height: 1.5;
    border-bottom: 1px solid var(--border-ghost);

    &:last-child { border-bottom: none; }

    .event-time {
      color: var(--text-muted);
      font-family: var(--font-data);
      flex-shrink: 0;
    }
    .event-text { color: var(--text-primary); }

    &.event-error .event-text { color: var(--accent-cinnabar); }
    &.event-done .event-text { color: var(--accent-jade); font-weight: 600; }
    &.event-chapter .event-text { color: var(--accent-ember); }
    &.event-start .event-text { color: var(--accent-aurora); font-weight: 600; }
  }
}

.propositions-card {
  grid-column: 1 / -1;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
}

.grid-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-ghost);
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
}

.chapter-review-panel {
  margin-bottom: var(--sp-lg);

  .review-header {
    display: flex;
    align-items: center;
    gap: var(--sp-sm);
    margin-bottom: var(--sp-md);
  }

  .review-body {
    background: var(--bg-elevated);
    border: 1px solid var(--accent-ember-dim);
    border-radius: 6px;
    padding: var(--sp-lg);
  }

  .review-summary {
    margin-bottom: var(--sp-md);
    padding-bottom: var(--sp-md);
    border-bottom: 1px solid var(--border-ghost);
  }

  .review-chapter-label {
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    font-weight: 600;
    color: var(--accent-ember);
  }

  .review-chapter-summary {
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    margin: var(--sp-xs) 0 0 0;
  }

  .review-guidance {
    margin-bottom: var(--sp-md);
  }

  .guidance-label {
    display: block;
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    margin-bottom: var(--sp-xs);
  }

  .review-actions {
    display: flex;
    gap: var(--sp-sm);
  }
}
</style>
