<template>
  <div class="stats-wrap">
    <span class="card-title">世界统计</span>
    <div class="stats-grid">
      <div class="stat-item">
        <span class="stat-value font-data">{{ godDecisionCount }}</span>
        <span class="stat-label">命运决策</span>
      </div>
      <div class="stat-item">
        <span class="stat-value font-data">{{ eventCount }}</span>
        <span class="stat-label">世界事件</span>
      </div>
      <div class="stat-item">
        <span class="stat-value font-data">{{ wordCount }}</span>
        <span class="stat-label">总字数</span>
      </div>
      <div class="stat-item">
        <span class="stat-value font-data">{{ plotThreadCount }}</span>
        <span class="stat-label">活跃剧情线</span>
      </div>
    </div>

    <!-- Token Consumption -->
    <div class="token-section" v-if="tokenTotal > 0">
      <div class="token-header">
        <span class="section-label" style="margin-bottom: 0;">Token 消耗</span>
        <span class="token-total font-data">{{ formatTokens(tokenTotal) }}</span>
      </div>
      <div class="token-breakdown" v-if="tokenByRole.length">
        <div v-for="r in tokenByRole" :key="r.role" class="token-role-row">
          <span class="role-name">{{ roleLabels[r.role] || r.role }}</span>
          <div class="role-bar-wrapper">
            <div
              class="role-bar"
              :style="{ width: `${Math.round((r.total_tokens / tokenTotal) * 100)}%` }"
            ></div>
          </div>
          <span class="role-tokens font-data">{{ formatTokens(r.total_tokens) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { onWSEvent } from '@/composables/useWebSocket'
import client from '@/api/client'

const godDecisionCount = ref(0)
const eventCount = ref(0)
const wordCount = ref('0')
const plotThreadCount = ref(0)
const tokenTotal = ref(0)
const tokenByRole = ref<{ role: string; total_tokens: number }[]>([])

const roleLabels: Record<string, string> = {
  director: '导演',
  character: '角色',
  writer: '写手',
  god: '命运',
  reviewer: '审校',
  reflection: '反思',
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

async function loadStats() {
  try {
    const [timelineRes, godRes, novelRes, threadsRes] = await Promise.all([
      client.get('/timeline'),
      client.get('/god-decisions'),
      client.get('/novel-full'),
      client.get('/plot-threads'),
    ])
    eventCount.value = (timelineRes.data.events || []).length
    godDecisionCount.value = (godRes.data.decisions || []).length
    const wc = novelRes.data.word_count || 0
    wordCount.value = wc > 10000 ? `${(wc / 10000).toFixed(1)}万` : wc.toLocaleString()
    plotThreadCount.value = (threadsRes.data.plot_threads || []).filter((t: any) => t.status === 'active').length
  } catch {
    // Silently handle
  }
}

async function loadTokenStats() {
  try {
    const res = await client.get('/token-stats')
    tokenTotal.value = res.data.total?.total_tokens || 0
    tokenByRole.value = res.data.by_role || []
  } catch {
    // Silently handle
  }
}

onMounted(() => {
  loadStats()
  loadTokenStats()
})

// Auto-refresh token stats on WS events
const unsub = onWSEvent('token_update', () => {
  loadTokenStats()
})
onUnmounted(() => unsub())
</script>

<style scoped lang="scss">
.stats-wrap { /* container */ }

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

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-md);
}

.stat-item {
  text-align: left;
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-muted);

  .stat-value {
    display: block;
    font-family: var(--font-data);
    font-size: var(--fs-xl);
    font-weight: 650;
    color: var(--accent-ember);
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
  }

  .stat-label {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    color: var(--text-muted);
    margin-top: 3px;
    display: block;
  }
}

.token-section {
  margin-top: var(--sp-lg);
  padding-top: var(--sp-md);
  border-top: 1px solid var(--border-default);
}

.token-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-sm);

  .token-total {
    font-size: var(--fs-md);
    font-weight: 650;
    color: var(--accent-ember);
  }
}

.token-breakdown {
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
}

.token-role-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);

  .role-name {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    color: var(--text-secondary);
    min-width: 36px;
  }

  .role-bar-wrapper {
    flex: 1;
    height: 5px;
    background: var(--bg-elevated);
    border-radius: 3px;
    overflow: hidden;
  }

  .role-bar {
    height: 100%;
    background: linear-gradient(90deg, #d97706, #f59e0b);
    border-radius: 3px;
    min-width: 2px;
    transition: width 0.4s var(--ease-out-expo);
  }

  .role-tokens {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    min-width: 40px;
    text-align: right;
  }
}
</style>