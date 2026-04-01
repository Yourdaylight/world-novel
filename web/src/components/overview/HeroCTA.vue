<template>
  <div class="hero-cta" :class="heroClass">
    <!-- First time: Start generation -->
    <div v-if="state === 'idle'" class="hero-inner">
      <div class="hero-info">
        <h2 class="hero-heading">开始生成</h2>
        <p class="hero-desc">基于三个终极命题，AI 将自动生成世界观、角色、时间线、伏笔和完整章节</p>
      </div>
      <div class="hero-actions">
        <el-select v-model="runMode" size="default" style="width: 160px;">
          <el-option label="全自动（旧版）" value="full" />
          <el-option label="逐章暂停（旧版）" value="chapter_by_chapter" />
          <el-option label="解耦模式" value="decoupled" />
        </el-select>
        <el-button type="primary" size="large" :loading="starting" @click="onStart">
          开始生成
        </el-button>
      </div>
    </div>

    <!-- Running: Link to live monitor -->
    <div v-else-if="state === 'running'" class="hero-inner hero-running" @click="goLive">
      <div class="hero-info">
        <h2 class="hero-heading">
          <span class="running-indicator">⚡</span>
          生成中...
        </h2>
        <p class="hero-desc">
          {{ currentPhaseLabel }}
          <span v-if="progressStore.completed > 0">
            — {{ progressStore.completed }}/{{ progressStore.total }}章
          </span>
          <span v-if="monitorStore.simulationBeatsTotal > 0">
            — 节拍 {{ monitorStore.simulationBeatsCompleted }}/{{ monitorStore.simulationBeatsTotal }}
          </span>
        </p>
      </div>
      <div class="hero-actions">
        <span class="hero-link">查看实时监控 →</span>
      </div>
    </div>

    <!-- Prepared: Simulation ready -->
    <div v-else-if="state === 'prepared'" class="hero-inner">
      <div class="hero-info">
        <h2 class="hero-heading">准备就绪</h2>
        <p class="hero-desc">世界观、角色、节拍规划已完成。可以开始模拟角色行动。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" :loading="starting" @click="onStartSimulation">
          开始模拟
        </el-button>
      </div>
    </div>

    <!-- Simulated: Ready to write -->
    <div v-else-if="state === 'simulated'" class="hero-inner">
      <div class="hero-info">
        <h2 class="hero-heading">模拟完成</h2>
        <p class="hero-desc">所有节拍模拟已完成，可以选择章节撰写叙事。</p>
      </div>
      <div class="hero-actions">
        <span class="hero-link" @click="goRead" style="cursor:pointer">去阅读/写作 →</span>
      </div>
    </div>

    <!-- Paused: Resume -->
    <div v-else-if="state === 'paused'" class="hero-inner">
      <div class="hero-info">
        <h2 class="hero-heading">已暂停</h2>
        <p class="hero-desc">已完成 {{ progressStore.completed }}/{{ progressStore.total }}章</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" :loading="starting" @click="onResume">
          继续生成第{{ progressStore.completed + 1 }}章
        </el-button>
      </div>
    </div>

    <!-- Done: Go read -->
    <div v-else-if="state === 'done'" class="hero-inner hero-done" @click="goRead">
      <div class="hero-info">
        <h2 class="hero-heading">已完成</h2>
        <p class="hero-desc">共 {{ progressStore.completed }} 章</p>
      </div>
      <div class="hero-actions">
        <span class="hero-link">去阅读 →</span>
      </div>
    </div>

    <!-- Error: Show error + restart -->
    <div v-else-if="state === 'error'" class="hero-inner hero-error">
      <div class="hero-info">
        <h2 class="hero-heading">生成出错</h2>
        <p class="hero-desc">{{ errorMessage || '未知错误' }}</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" :loading="starting" @click="onStart">
          重新开始
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useProgressStore } from '@/stores/progress'
import { useLiveMonitorStore } from '@/stores/liveMonitor'
import { startGeneration, resumeGeneration, startPreparation, startSimulation } from '@/api/novels'

const props = defineProps<{
  isRunning: boolean
  errorMessage?: string
  novelStatus?: string
}>()

const router = useRouter()
const route = useRoute()
const progressStore = useProgressStore()
const monitorStore = useLiveMonitorStore()
const runMode = ref('decoupled')
const starting = ref(false)

const state = computed(() => {
  if (progressStore.phase === 'error') return 'error'
  if (progressStore.phase === 'done') return 'done'
  if (props.novelStatus === 'prepared') return 'prepared'
  if (props.novelStatus === 'simulated') return 'simulated'
  if (progressStore.paused) return 'paused'
  if (props.isRunning) return 'running'
  return 'idle'
})

const heroClass = computed(() => `hero-${state.value}`)

const phaseLabels: Record<string, string> = {
  directing: '导演规划',
  world_building: '构建世界',
  foreshadow_planning: '伏笔网络',
  beat_planning: '节拍规划',
  simulating: '模拟角色场景',
  writing: '撰写章节',
  reviewing: '审校伏笔',
  god_deliberation: '命运裁决',
  god_checkpoint: '命运检查点',
}

const currentPhaseLabel = computed(() =>
  phaseLabels[progressStore.phase] || progressStore.phase || '处理中...'
)

function goLive() {
  const novelId = route.params.novelId
  router.push({ name: 'live', params: { novelId: novelId as string } })
}

function goRead() {
  const novelId = route.params.novelId
  router.push({ name: 'read', params: { novelId: novelId as string } })
}

async function onStart() {
  const novelId = route.params.novelId as string
  if (!novelId) return
  starting.value = true
  try {
    if (runMode.value === 'decoupled') {
      // V9: Start preparation graph only
      const res = await startPreparation(novelId)
      if (res.ok) {
        ElMessage.success('准备阶段已启动')
        goLive()
      } else {
        ElMessage.error(res.error || '启动失败')
      }
    } else {
      // Legacy: full or chapter_by_chapter
      const res = await startGeneration(novelId, runMode.value)
      if (res.ok) {
        ElMessage.success('生成已启动')
        goLive()
      } else {
        ElMessage.error(res.error || '启动失败')
      }
    }
  } finally {
    starting.value = false
  }
}

async function onStartSimulation() {
  const novelId = route.params.novelId as string
  if (!novelId) return
  starting.value = true
  try {
    const res = await startSimulation(novelId)
    if (res.ok) {
      ElMessage.success(`模拟已启动 (${res.beat_count || 0} 节拍)`)
      goLive()
    } else {
      ElMessage.error(res.error || '启动失败')
    }
  } finally {
    starting.value = false
  }
}

async function onResume() {
  const novelId = route.params.novelId as string
  if (!novelId) return
  starting.value = true
  try {
    const res = await resumeGeneration(novelId, runMode.value)
    if (res.ok) {
      ElMessage.success('继续生成已启动')
      goLive()
    } else {
      ElMessage.error(res.error || '恢复失败')
    }
  } finally {
    starting.value = false
  }
}
</script>

<style scoped lang="scss">
.hero-cta {
  margin-bottom: var(--sp-lg);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-default);
  overflow: hidden;
}

.hero-inner {
  background: var(--bg-surface);
  padding: var(--sp-lg) var(--sp-xl);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-xl);
}

.hero-info {
  flex: 1;
}

.hero-heading {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 var(--sp-xs) 0;
}

.hero-desc {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin: 0;
}

.hero-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: var(--sp-sm);
}

.hero-link {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--accent-ember);
  white-space: nowrap;
}

/* Running state */
.hero-running {
  cursor: pointer;
  border-left: 3px solid var(--accent-ember);

  &:hover {
    background: var(--bg-elevated);
  }

  .running-indicator {
    animation: pulse-icon 1.5s ease-in-out infinite;
  }
}

/* Done state */
.hero-done {
  cursor: pointer;
  border-left: 3px solid var(--accent-jade);

  &:hover {
    background: var(--bg-elevated);
  }

  .hero-link {
    color: var(--accent-jade);
  }
}

/* Error state */
.hero-error {
  border-left: 3px solid var(--accent-cinnabar);

  .hero-heading {
    color: var(--accent-cinnabar);
  }
}

/* Prepared state */
.hero-prepared {
  border-left: 3px solid var(--accent-jade);

  .hero-heading {
    color: var(--accent-jade);
  }
}

/* Simulated state */
.hero-simulated {
  border-left: 3px solid var(--accent-jade);

  .hero-heading {
    color: var(--accent-jade);
  }

  .hero-link {
    color: var(--accent-jade);
  }
}

@keyframes pulse-icon {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
