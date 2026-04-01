<template>
  <div class="live-monitor-page" v-loading="loading">
    <!-- Empty state when not generating -->
    <div class="monitor-empty" v-if="!hasActivity">
      <div class="empty-content">
        <h2 class="empty-title">生成监控</h2>
        <p class="empty-desc">开始生成后，此处将实时显示 Pipeline 阶段、角色行动和写作过程</p>
        <el-button type="primary" size="large" @click="goOverview" v-if="progressStore.phase === 'idle'">
          前往概览页开始生成
        </el-button>
      </div>
    </div>

    <!-- 3-column layout when active -->
    <div class="monitor-layout" v-else>
      <!-- Left: Pipeline Stepper -->
      <aside class="monitor-left">
        <PipelineStepper />
      </aside>

      <!-- Center: Stage content -->
      <main class="monitor-center">
        <div class="center-header">
          <h2 class="center-title">
            第{{ monitorStore.currentChapter + 1 }}章
            <span class="phase-badge">{{ monitorStore.phaseLabel }}</span>
          </h2>
        </div>

        <div class="center-stage">
          <!-- Simulating stage -->
          <StageSimulating v-if="monitorStore.activeStage === 'simulating'" />

          <!-- Writing stage -->
          <StageWriting v-else-if="monitorStore.activeStage === 'writing'" />

          <!-- God decision -->
          <StageGodDecision v-else-if="monitorStore.activeStage === 'god_decision'" />

          <!-- Chapter complete -->
          <ChapterCompleteCard v-else-if="monitorStore.activeStage === 'chapter_complete'" />

          <!-- Waiting / Other stages -->
          <StageWaiting v-else />
        </div>
      </main>

      <!-- Right: Event Log -->
      <aside class="monitor-right">
        <MonitorEventLog />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useLiveMonitorStore } from '@/stores/liveMonitor'
import { useProgressStore } from '@/stores/progress'
import { useEventLogStore } from '@/stores/eventLog'
import { onWSEvent } from '@/composables/useWebSocket'
import PipelineStepper from './PipelineStepper.vue'
import MonitorEventLog from './MonitorEventLog.vue'
import StageSimulating from './StageSimulating.vue'
import StageWriting from './StageWriting.vue'
import StageWaiting from './StageWaiting.vue'
import StageGodDecision from './StageGodDecision.vue'
import ChapterCompleteCard from './ChapterCompleteCard.vue'

const router = useRouter()
const route = useRoute()
const monitorStore = useLiveMonitorStore()
const progressStore = useProgressStore()
const eventLogStore = useEventLogStore()

const loading = ref(true)

const hasActivity = computed(() => {
  // Still loading — don't show empty state yet
  if (loading.value) return true
  return monitorStore.currentPhase !== 'idle' ||
    eventLogStore.entries.length > 0 ||
    progressStore.phase !== 'idle' ||
    progressStore.completed > 0 ||
    progressStore.paused
})

function goOverview() {
  const novelId = route.params.novelId
  router.push({ name: 'overview', params: { novelId: novelId as string } })
}

// Wire up WS events to the monitor store
const unsubs: (() => void)[] = []

onMounted(async () => {
  // Load progress from API on mount (handles page refresh)
  await progressStore.loadProgress()

  // Sync monitor store from progress store
  if (progressStore.phase && progressStore.phase !== 'idle') {
    monitorStore.currentPhase = progressStore.phase
  }
  if (progressStore.completed > 0) {
    monitorStore.currentChapter = progressStore.completed - 1
  }
  // If paused or done but has completed chapters, show the last state
  if (progressStore.paused && progressStore.completed > 0) {
    monitorStore.currentPhase = 'simulating' // Show last known active state
    monitorStore.chapterCompleted = true
  }

  loading.value = false

  unsubs.push(onWSEvent('phase_change', (e) => monitorStore.handlePhaseChange(e)))
  unsubs.push(onWSEvent('agent_turn', (e) => monitorStore.handleAgentTurn(e)))
  unsubs.push(onWSEvent('agent_evaluate', (e) => monitorStore.handleAgentEvaluate(e)))
  unsubs.push(onWSEvent('agent_tool_call', (e) => monitorStore.handleAgentToolCall(e)))
  unsubs.push(onWSEvent('token', (e) => monitorStore.handleToken(e)))
  unsubs.push(onWSEvent('chapter_start', (e) => monitorStore.handleChapterStart(e)))
  unsubs.push(onWSEvent('chapter_completed', (e) => monitorStore.handleChapterCompleted(e)))
  unsubs.push(onWSEvent('scene_simulated', (e) => monitorStore.handleSceneSimulated(e)))
  unsubs.push(onWSEvent('god_decision', (e) => monitorStore.handleGodDecision(e)))
  unsubs.push(onWSEvent('generation_finished', () => monitorStore.handleGenerationFinished()))
  unsubs.push(onWSEvent('generation_started', () => {
    monitorStore.reset()
    monitorStore.currentPhase = 'directing'
  }))

  // V9: Decoupled pipeline events
  unsubs.push(onWSEvent('preparation_started', () => monitorStore.handlePreparationStarted()))
  unsubs.push(onWSEvent('preparation_finished', (e) => monitorStore.handlePreparationFinished(e)))
  unsubs.push(onWSEvent('simulation_started', (e) => monitorStore.handleSimulationStarted(e)))
  unsubs.push(onWSEvent('simulation_finished', (e) => monitorStore.handleSimulationFinished(e)))
  unsubs.push(onWSEvent('beat_simulated', (e) => monitorStore.handleBeatSimulated(e)))
  unsubs.push(onWSEvent('beat_plan_completed', (e) => monitorStore.handleBeatPlanCompleted(e)))
  unsubs.push(onWSEvent('simulation_progress', (e) => monitorStore.handleSimulationProgress(e)))
})

onUnmounted(() => {
  unsubs.forEach(fn => fn())
})
</script>

<style scoped lang="scss">
.live-monitor-page {
  min-height: calc(100vh - var(--sp-xl) * 2);
}

/* Empty state */
.monitor-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.empty-content {
  text-align: center;
  max-width: 400px;
}

.empty-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 var(--sp-sm) 0;
}

.empty-desc {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
  margin: 0 0 var(--sp-lg) 0;
  line-height: 1.6;
}

/* 3-column layout */
.monitor-layout {
  display: grid;
  grid-template-columns: 180px 1fr 280px;
  gap: var(--sp-lg);
  min-height: calc(100vh - var(--sp-xl) * 2);
}

.monitor-left {
  padding-top: var(--sp-sm);
}

.monitor-center {
  min-width: 0;
}

.monitor-right {
  padding-top: var(--sp-sm);
}

.center-header {
  margin-bottom: var(--sp-md);
  padding-bottom: var(--sp-sm);
  border-bottom: 1px solid var(--border-rule);
}

.center-title {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
}

.phase-badge {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 500;
  color: var(--accent-ember);
  background: var(--accent-ember-dim);
  padding: 2px 8px;
  border-radius: 4px;
}

.center-stage {
  min-height: 400px;
}
</style>
