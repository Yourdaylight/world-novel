<template>
  <div class="pipeline-stepper">
    <!-- Preparation phase (one-time) -->
    <div class="stepper-section">
      <span class="section-label">准备</span>
      <div class="stepper-steps">
        <div
          v-for="step in monitorStore.preparationSteps"
          :key="step.key"
          class="step-item"
          :class="{
            active: step.key === monitorStore.currentPhase,
            completed: monitorStore.completedPreparation.has(step.key) || isPrepDone,
          }"
        >
          <span class="step-indicator">
            <span v-if="monitorStore.completedPreparation.has(step.key) || isPrepDone" class="step-check">✓</span>
            <span v-else-if="step.key === monitorStore.currentPhase" class="step-dot active-dot"></span>
            <span v-else class="step-dot"></span>
          </span>
          <span class="step-label">{{ step.label }}</span>
        </div>
      </div>
    </div>

    <!-- Chapter activities (decoupled, per-chapter) -->
    <div class="stepper-section">
      <span class="section-label" v-if="monitorStore.isSimulationRunning || monitorStore.simulationBeatsTotal > 0">
        模拟 ({{ monitorStore.simulationBeatsCompleted }}/{{ monitorStore.simulationBeatsTotal }})
      </span>
      <span class="section-label" v-else>
        第{{ monitorStore.currentChapter + 1 }}章
      </span>

      <!-- V9: Beat progress bar -->
      <div class="beat-progress" v-if="monitorStore.simulationBeatsTotal > 0">
        <el-progress
          :percentage="beatPercent"
          :stroke-width="4"
          :show-text="false"
          color="#d4793a"
        />
        <span class="beat-label" v-if="monitorStore.currentBeatId">
          {{ monitorStore.currentBeatId }}
        </span>
      </div>

      <div class="activity-grid">
        <div
          v-for="act in monitorStore.chapterActivities"
          :key="act.key"
          class="activity-card"
          :class="{
            active: act.key === monitorStore.currentPhase,
            idle: act.key !== monitorStore.currentPhase,
          }"
        >
          <div class="activity-header">
            <span class="activity-dot" :class="act.key === monitorStore.currentPhase ? 'dot-active' : 'dot-idle'"></span>
            <span class="activity-name">{{ act.label }}</span>
          </div>
          <span class="activity-desc">{{ act.desc }}</span>
        </div>
      </div>
      <div class="decoupled-hint" v-if="!monitorStore.isPreparationPhase">
        模拟与写作共享时间线，独立运行
      </div>
    </div>

    <!-- Footer stats -->
    <div class="stepper-footer">
      <div class="footer-stat">
        <span class="stat-label">章节</span>
        <span class="stat-value font-data">{{ progressStore.completed }}/{{ progressStore.total || '?' }}</span>
      </div>
      <div class="footer-progress">
        <el-progress
          :percentage="progressStore.percent"
          :stroke-width="4"
          :show-text="false"
          color="#d4793a"
        />
      </div>
      <div class="footer-stat" v-if="tokenTotal > 0">
        <span class="stat-label">Token</span>
        <span class="stat-value font-data">{{ formatTokens(tokenTotal) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useLiveMonitorStore } from '@/stores/liveMonitor'
import { useProgressStore } from '@/stores/progress'
import client from '@/api/client'

const monitorStore = useLiveMonitorStore()
const progressStore = useProgressStore()
const tokenTotal = ref(0)

// All preparation steps done once we're past them
const isPrepDone = computed(() => {
  const phase = monitorStore.currentPhase
  return !monitorStore.isPreparationPhase && phase !== 'idle'
})

// V9: Beat simulation progress
const beatPercent = computed(() => {
  const t = monitorStore.simulationBeatsTotal
  return t > 0 ? Math.round((monitorStore.simulationBeatsCompleted / t) * 100) : 0
})

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

async function loadTokens() {
  try {
    const res = await client.get('/token-stats')
    tokenTotal.value = res.data.total?.total_tokens || 0
  } catch { /* ignore */ }
}

onMounted(() => { loadTokens() })
</script>

<style scoped lang="scss">
.pipeline-stepper {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: var(--sp-md);
}

.stepper-section {
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
}

.section-label {
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  padding-bottom: var(--sp-xs);
  border-bottom: 1px solid var(--border-default);
}

/* Preparation steps — linear, compact */
.stepper-steps {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
  padding: 3px var(--sp-xs);
  border-radius: 3px;
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);

  &.active {
    color: var(--accent-ember);
    background: var(--accent-ember-dim);
    font-weight: 500;
  }

  &.completed {
    color: var(--text-secondary);
  }
}

.step-indicator {
  width: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-muted);

  &.active-dot {
    background: var(--accent-ember);
    animation: pulse-dot 2s ease-in-out infinite;
  }
}

.step-check {
  font-size: 9px;
  color: var(--accent-jade);
  font-weight: 700;
}

/* Chapter activities — grid cards, not linear */
.activity-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.activity-card {
  padding: var(--sp-xs) var(--sp-sm);
  border-radius: 4px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  transition: border-color 150ms ease;

  &.active {
    border-color: var(--accent-ember);
    background: var(--accent-ember-dim);
  }

  &.idle {
    opacity: 0.6;
  }
}

.activity-header {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
}

.activity-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;

  &.dot-active {
    background: var(--accent-ember);
    animation: pulse-dot 2s ease-in-out infinite;
  }

  &.dot-idle {
    background: var(--text-muted);
  }
}

.activity-name {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 500;
  color: var(--text-primary);
}

.activity-desc {
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--text-muted);
  margin-left: calc(5px + var(--sp-xs));
  display: block;
}

.decoupled-hint {
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--text-muted);
  font-style: italic;
  margin-top: var(--sp-xs);
  padding: var(--sp-xs);
  border-left: 2px solid var(--border-default);
}

/* V9: Beat progress */
.beat-progress {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: var(--sp-xs);
}

.beat-label {
  font-family: var(--font-data);
  font-size: 9px;
  color: var(--text-muted);
  text-align: right;
}

/* Footer */
.stepper-footer {
  margin-top: auto;
  border-top: 1px solid var(--border-default);
  padding-top: var(--sp-sm);
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
}

.footer-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.stat-value {
  font-size: var(--fs-xs);
  color: var(--text-secondary);
}

.footer-progress {
  padding: var(--sp-xs) 0;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.4); }
}
</style>
