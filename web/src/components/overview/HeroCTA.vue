<template>
  <div class="hero-cta" :class="heroClass">
    <!-- Idle: Start generation -->
    <div v-if="state === 'idle'" class="hero-inner hero-idle">
      <div class="hero-info">
        <h2 class="hero-heading">开始生成</h2>
        <p class="hero-desc">基于三个终极命题，AI 将自动生成世界观、角色、时间线、伏笔和完整章节</p>
      </div>
      <div class="hero-actions">
        <el-select v-model="runMode" size="default" style="width: 140px;">
          <el-option label="解耦模式" value="decoupled" />
        </el-select>
        <button class="hero-btn hero-btn-primary" :disabled="starting" @click="onStart">
          <span v-if="starting" class="btn-spinner"></span>
          <template v-else>开始生成</template>
        </button>
      </div>
    </div>

    <!-- Running: Link to live monitor -->
    <div v-else-if="state === 'running'" class="hero-inner hero-running" @click="goLive">
      <div class="hero-info">
        <div class="hero-status-badge running-badge">
          <span class="badge-dot"></span>
          生成中
        </div>
        <h2 class="hero-heading">{{ currentPhaseLabel }}</h2>
        <p class="hero-desc">
          {{ progressStore.completed }}/{{ progressStore.total }}章
          <template v-if="monitorStore.simulationBeatsTotal > 0">
            · 节拍 {{ monitorStore.simulationBeatsCompleted }}/{{ monitorStore.simulationBeatsTotal }}
          </template>
        </p>
      </div>
      <div class="hero-actions">
        <span class="hero-link">查看实时监控 →</span>
      </div>
    </div>

    <!-- Prepared: Simulation ready -->
    <div v-else-if="state === 'prepared'" class="hero-inner hero-prepared">
      <div class="hero-info">
        <div class="hero-status-badge ready-badge">准备就绪</div>
        <p class="hero-desc">世界观、角色、节拍规划已完成。可以开始模拟角色行动。</p>
      </div>
      <div class="hero-actions">
        <button class="hero-btn hero-btn-primary" :disabled="starting" @click="onStartSimulation">
          开始模拟
        </button>
      </div>
    </div>

    <!-- Simulated: Ready to write -->
    <div v-else-if="state === 'simulated'" class="hero-inner hero-simulated" @click="goRead">
      <div class="hero-info">
        <div class="hero-status-badge done-badge">模拟完成</div>
        <p class="hero-desc">所有节拍模拟已完成，可以选择章节撰写叙事。</p>
      </div>
      <div class="hero-actions">
        <span class="hero-link">去阅读/写作 →</span>
      </div>
    </div>

    <!-- Paused: Resume -->
    <div v-else-if="state === 'paused'" class="hero-inner hero-paused">
      <div class="hero-info">
        <div class="hero-status-badge paused-badge">已暂停</div>
        <p class="hero-desc">已完成 {{ progressStore.completed }}/{{ progressStore.total }}章</p>
      </div>
      <div class="hero-actions">
        <button class="hero-btn hero-btn-primary" :disabled="starting" @click="onResume">
          继续第{{ progressStore.completed + 1 }}章
        </button>
      </div>
    </div>

    <!-- Done: Go read -->
    <div v-else-if="state === 'done'" class="hero-inner hero-done" @click="goRead">
      <div class="hero-info">
        <div class="hero-status-badge done-badge">已完成</div>
        <p class="hero-desc">共 {{ progressStore.completed }} 章</p>
      </div>
      <div class="hero-actions">
        <span class="hero-link done-link">去阅读 →</span>
      </div>
    </div>

    <!-- Error: Show error + restart -->
    <div v-else-if="state === 'error'" class="hero-inner hero-error">
      <div class="hero-info">
        <div class="hero-status-badge error-badge">出错</div>
        <p class="hero-desc">{{ errorMessage || '未知错误' }}</p>
      </div>
      <div class="hero-actions">
        <button class="hero-btn hero-btn-danger" :disabled="starting" @click="onStart">
          重新开始
        </button>
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
      const res = await startPreparation(novelId)
      if (res.ok) {
        ElMessage.success('准备阶段已启动')
        goLive()
      } else {
        ElMessage.error(res.error || '启动失败')
      }
    } else {
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
/* === Hero CTA — premium card system === */
.hero-cta {
  margin-bottom: var(--sp-lg);
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
}

.hero-inner {
  padding: var(--sp-lg) var(--sp-xl);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-xl);
  transition: background var(--duration-base) ease;
}

.hero-info {
  flex: 1;
  min-width: 0;
}

/* Status badges */
.hero-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 650;
  padding: 4px 12px;
  border-radius: 20px;
  letter-spacing: 0.03em;
  margin-bottom: var(--sp-sm);

  &.running-badge {
    color: #d97706;
    background: rgba(217,119,6,0.09);
    .badge-dot {
      width: 6px; height: 6px;
      border-radius: 50%;
      background: currentColor;
      animation: dot-pulse 2s ease-in-out infinite;
    }
  }

  &.ready-badge {
    color: #2563eb;
    background: rgba(37,99,235,0.08);
  }

  &.done-badge {
    color: #059669;
    background: rgba(5,150,105,0.08);
  }

  &.paused-badge {
    color: #6b7280;
    background: rgba(107,114,128,0.08);
  }

  &.error-badge {
    color: #dc2626;
    background: rgba(220,38,38,0.08);
  }
}

.hero-heading {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  line-height: 1.25;
  letter-spacing: -0.02em;
}

.hero-desc {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.55;
}

/* Actions area */
.hero-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: var(--sp-sm);
}

/* Primary button */
.hero-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 11px 24px;
  border-radius: var(--radius-md);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 600;
  cursor: pointer;
  border: none;
  white-space: nowrap;
  transition: all var(--duration-base) ease;
  letter-spacing: 0.01em;

  &.hero-btn-primary {
    background: linear-gradient(135deg, #d97706, #b45309);
    color: #fff;
    box-shadow: 0 2px 10px rgba(217,119,6,0.28);

    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 5px 18px rgba(217,119,6,0.40);
    }

    &:active:not(:disabled) {
      transform: translateY(0);
    }
  }

  &.hero-btn-danger {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    color: #fff;

    &:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: 0 4px 14px rgba(220,38,38,0.3);
    }
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-spinner {
  width: 15px; height: 15px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

/* Links */
.hero-link {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 550;
  color: var(--accent-ember);
  cursor: pointer;
  white-space: nowrap;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  transition: all var(--duration-base) ease;

  &:hover {
    background: rgba(217,119,6,0.06);
  }
}

.done-link { color: var(--accent-jade); &:hover { background: rgba(5,150,105,0.06); } }

/* State variants */
.hero-running,
.hero-done,
.hero-simulated {
  cursor: pointer;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
  }

  &:hover { background: var(--bg-elevated); }
}
.hero-running::before { background: #d97706; }
.hero-done::before,
.hero-simulated::before { background: #059669; }

.hero-error::before,
.hero-paused::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}
.hero-error::before { background: #dc2626; }
.hero-paused::before { background: #6b7280; }

@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.35; transform: scale(0.85); }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>