<template>
  <div class="overview-page" v-loading="loading">
    <!-- 🚀 Generation Action Panel -->
    <div class="generation-panel ledger-rule">
      <div class="gen-panel-inner">
        <div class="gen-info">
          <h2 v-if="isIdle && !worldStatus.is_running">开始创世</h2>
          <h2 v-else-if="worldStatus.is_running || worldStatus.status === 'generating'">创世进行中</h2>
          <h2 v-else-if="worldStatus.status === 'paused'">创世已暂停</h2>
          <h2 v-else-if="worldStatus.status === 'completed'">创世完成</h2>
          <h2 v-else>开始创世</h2>

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
          <!-- 首次创世 -->
          <el-button
            v-if="canStartFresh"
            type="success"
            size="large"
            :loading="starting"
            @click="onStartGeneration"
          >
            开始创世
          </el-button>
          <!-- 继续生成 (从检查点恢复) -->
          <el-button
            v-if="canResume"
            type="primary"
            size="large"
            :loading="starting"
            @click="onResumeGeneration"
          >
            ▶ 继续生成
          </el-button>
          <!-- 暂停 -->
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

    <!-- 📡 Real-time Event Log (visible when running or has events) -->
    <div class="event-log-panel ledger-rule" v-if="eventLog.length > 0">
      <div class="event-log-header">
        <span class="section-label">实时事件日志</span>
        <el-button text size="small" @click="eventLog = []">清空</el-button>
      </div>
      <div class="event-log-body" ref="logContainer">
        <div
          v-for="(evt, i) in eventLog"
          :key="i"
          :class="['event-item', `event-${evt.type}`]"
        >
          <span class="event-time">{{ evt.time }}</span>
          <span class="event-icon">{{ evt.icon }}</span>
          <span class="event-text">{{ evt.text }}</span>
        </div>
      </div>
    </div>

    <!-- Propositions Section -->
    <div class="propositions-section ledger-rule" v-if="hasPropositions">
      <span class="section-label">三个终极命题</span>
      <el-row :gutter="16" class="propositions-row">
        <el-col :span="8">
          <PropositionCard icon="🔵" label="是什么" :text="propositions.what_is" color="blue" />
        </el-col>
        <el-col :span="8">
          <PropositionCard icon="🟢" label="从何来" :text="propositions.where_from" color="green" />
        </el-col>
        <el-col :span="8">
          <PropositionCard icon="🔴" label="往何去" :text="propositions.where_to" color="red" />
        </el-col>
      </el-row>
    </div>

    <el-row :gutter="20" style="margin-top: var(--sp-lg)">
      <el-col :span="12">
        <NovelInfoCard />
      </el-col>
      <el-col :span="12">
        <WorldStats />
      </el-col>
    </el-row>

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
import PropositionCard from './PropositionCard.vue'
import WorldStats from './WorldStats.vue'
import { useWorldStore } from '@/stores/world'
import { useProgressStore } from '@/stores/progress'
import { fetchPropositions, startGeneration, resumeGeneration, pauseGeneration } from '@/api/novels'
import client from '@/api/client'
import { useLiveWritingStore } from '@/stores/liveWriting'

const route = useRoute()
const worldStore = useWorldStore()
const progressStore = useProgressStore()
const liveWritingStore = useLiveWritingStore()
const loading = ref(false)
const starting = ref(false)
const pausing = ref(false)
const runMode = ref('full')
const logContainer = ref<HTMLElement | null>(null)

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

interface LogEntry { time: string; icon: string; text: string; type: string }
const eventLog = ref<LogEntry[]>([])

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

const phaseLabels: Record<string, string> = {
  directing: '📋 导演规划中 — 构建故事大纲',
  world_building: '🌍 构建世界观',
  foreshadow_planning: '📊 规划伏笔系统',
  simulating: '🎭 模拟角色场景',
  writing: '✍️ 撰写章节',
  reviewing: '🔍 审校伏笔',
  god_deliberation: '🔮 命运裁决',
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
let wsHandler: ((event: any) => void) | null = null

async function pollStatus() {
  const novelId = route.params.novelId as string
  if (!novelId) return
  try {
    const { data } = await client.get(`/worlds/${novelId}/status`)
    Object.assign(worldStatus, data)
    // Also update progress store
    if (data.progress) {
      progressStore.updateFromWS(data.progress)
    }
  } catch { /* ignore */ }
}

function addEvent(icon: string, text: string, type: string = 'info') {
  const now = new Date()
  const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  eventLog.value.push({ time, icon, text, type })
  // Keep last 50
  if (eventLog.value.length > 50) eventLog.value.shift()
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

function setupWSListener() {
  // Listen to the liveWritingStore events
  wsHandler = (event: any) => {
    const t = event.type
    if (t === 'phase_change') {
      const label = phaseLabels[event.phase] || event.phase
      addEvent('🔄', `阶段切换: ${label}`, 'phase')
      worldStatus.progress.phase = event.phase
      if (event.phase !== 'idle' && event.phase !== 'done') {
        worldStatus.is_running = true
        worldStatus.status = 'generating'
      }
    } else if (t === 'scene_simulated') {
      addEvent('🎭', `场景模拟完成: 第${event.chapter + 1}章 场景${event.scene + 1} (${event.action_count}个行动)`, 'scene')
    } else if (t === 'scene_written') {
      addEvent('✍️', `场景写作完成: 第${event.chapter + 1}章 场景${event.scene + 1} (${event.word_count}字)`, 'write')
    } else if (t === 'chapter_completed') {
      addEvent('📖', `第${event.chapter + 1}章完成: ${event.title} (${event.word_count}字)`, 'chapter')
      worldStatus.chapters_completed = event.chapter + 1
    } else if (t === 'god_decision') {
      const events = event.events?.join('、') || ''
      addEvent('🔮', `命运裁决: ${events} ${event.guidance?.substring(0, 60) || ''}`, 'god')
    } else if (t === 'checkpoint_saved') {
      addEvent('💾', `检查点已保存 (${event.chapters_completed}章完成)`, 'checkpoint')
    } else if (t === 'generation_started') {
      addEvent('🚀', '创世流程已启动！', 'start')
      worldStatus.is_running = true
      worldStatus.status = 'generating'
    } else if (t === 'generation_finished') {
      addEvent('🎉', `创世完成！状态: ${event.status}`, 'done')
      worldStatus.is_running = false
      worldStatus.status = event.status || 'completed'
      // Reload data
      worldStore.loadWorld()
      pollStatus()
    } else if (t === 'generation_error') {
      addEvent('❌', `创世出错: ${event.error}`, 'error')
      worldStatus.is_running = false
      worldStatus.status = 'idle'
    } else if (t === 'novel_completed') {
      addEvent('📚', `小说完成: ${event.title} (${event.word_count}字, ${event.total_chapters}章)`, 'done')
    }
  }
  liveWritingStore.$onAction(({ name, args }) => {
    if (name === 'handleEvent' && wsHandler) {
      wsHandler(args[0])
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

  // Poll every 3s
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
      ElMessage.success('创世已启动！')
      addEvent('🚀', '创世请求已发送，等待 AI 响应...', 'start')
      worldStatus.is_running = true
      worldStatus.status = 'generating'
    } else {
      ElMessage.error(res.error || '启动失败')
      addEvent('❌', `启动失败: ${res.error}`, 'error')
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
      addEvent('▶', `从第${worldStatus.chapters_completed + 1}章继续生成（新设定已融入）`, 'start')
      worldStatus.is_running = true
      worldStatus.status = 'generating'
    } else {
      ElMessage.error(res.error || '恢复失败')
      addEvent('❌', `恢复失败: ${res.error}`, 'error')
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
      addEvent('⏸', '生成已暂停', 'phase')
      worldStatus.is_running = false
      worldStatus.status = 'paused'
    }
  } finally {
    pausing.value = false
  }
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
      font-family: var(--font-ui);
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
    .event-icon { flex-shrink: 0; }
    .event-text { color: var(--text-primary); }

    &.event-error .event-text { color: var(--accent-cinnabar); }
    &.event-done .event-text { color: var(--accent-jade); font-weight: 600; }
    &.event-chapter .event-text { color: var(--accent-ember); }
    &.event-start .event-text { color: var(--accent-aurora); font-weight: 600; }
  }
}

.propositions-section {
  padding-top: var(--sp-md);
}

.propositions-row {
  margin-top: var(--sp-md);
}
</style>
