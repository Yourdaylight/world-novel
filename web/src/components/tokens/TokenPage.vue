<template>
  <div class="token-page">
    <!-- Section: Total -->
    <header class="page-header">
      <h2 class="page-title">Token 消耗</h2>
      <span class="page-subtitle">资源追踪与分析</span>
    </header>

    <div class="ledger-rule" />

    <!-- Total Panel -->
    <section class="totals-section">
      <div class="total-item">
        <span class="total-label">总 Token</span>
        <span class="total-value font-data">{{ formatNum(stats.total.total_tokens) }}</span>
      </div>
      <div class="total-item">
        <span class="total-label">Prompt</span>
        <span class="total-value font-data prompt-color">{{ formatNum(stats.total.prompt_tokens) }}</span>
      </div>
      <div class="total-item">
        <span class="total-label">Completion</span>
        <span class="total-value font-data completion-color">{{ formatNum(stats.total.completion_tokens) }}</span>
      </div>
    </section>

    <div class="ledger-rule" />

    <!-- By Role -->
    <section class="role-section">
      <h3 class="section-label">按角色分布</h3>
      <div class="role-list">
        <div v-for="r in stats.by_role" :key="r.role" class="role-row">
          <div class="role-info">
            <span class="role-name">{{ r.role }}</span>
            <span class="role-pct font-data">{{ rolePct(r) }}%</span>
          </div>
          <div class="role-bar-track">
            <div
              class="role-bar-fill prompt-bar"
              :style="{ width: barWidth(r.prompt_tokens) }"
            />
            <div
              class="role-bar-fill completion-bar"
              :style="{ width: barWidth(r.completion_tokens), left: barWidth(r.prompt_tokens) }"
            />
          </div>
          <div class="role-nums font-data">
            <span class="prompt-color">{{ formatTokens(r.prompt_tokens) }}</span>
            <span class="text-muted">/</span>
            <span class="completion-color">{{ formatTokens(r.completion_tokens) }}</span>
          </div>
        </div>
      </div>
    </section>

    <div class="ledger-rule" />

    <!-- By Chapter Trend -->
    <section class="chart-section">
      <h3 class="section-label">按章节趋势</h3>
      <div ref="chapterChartEl" class="chart-container" />
    </section>

    <div class="ledger-rule" />

    <!-- By Chapter × Role Stacked -->
    <section class="chart-section">
      <h3 class="section-label">章节 × 角色消耗</h3>
      <div ref="stackedChartEl" class="chart-container chart-container--tall" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { onWSEvent } from '@/composables/useWebSocket'
import client from '@/api/client'
import * as echarts from 'echarts'

// ---------- Types ----------
interface TokenTotal {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

interface RoleRow {
  role: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

interface ChapterRow {
  chapter_index: number
  total_tokens: number
}

interface ChapterRoleRow {
  chapter_index: number
  role: string
  total_tokens: number
}

interface Stats {
  total: TokenTotal
  by_role: RoleRow[]
  by_chapter: ChapterRow[]
  by_chapter_and_role: ChapterRoleRow[]
}

// ---------- State ----------
const stats = ref<Stats>({
  total: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  by_role: [],
  by_chapter: [],
  by_chapter_and_role: [],
})

const chapterChartEl = ref<HTMLElement | null>(null)
const stackedChartEl = ref<HTMLElement | null>(null)
let chapterChart: echarts.ECharts | null = null
let stackedChart: echarts.ECharts | null = null

// ---------- Formatters ----------
function formatNum(n: number): string {
  return n.toLocaleString()
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

function rolePct(r: RoleRow): string {
  const total = stats.value.total.total_tokens
  if (!total) return '0'
  return ((r.total_tokens / total) * 100).toFixed(1)
}

function barWidth(tokens: number): string {
  const maxRole = stats.value.by_role[0]?.total_tokens || 1
  return `${(tokens / maxRole) * 100}%`
}

// ---------- ECharts Theming ----------
const EMBER = '#d4793a'
const EMBER_DIM = 'rgba(212, 121, 58, 0.15)'
const JADE = '#4ec994'
const AURORA = '#a67fd4'
const CINNABAR = '#e04545'
const PHOSPHOR = '#c6e847'
const SILVER = '#c8bfd4'
const TEXT_SECONDARY = '#9e8fa3'
const TEXT_MUTED = '#58505f'
const BORDER_RULE = 'rgba(237, 230, 216, 0.10)'

const ROLE_COLORS: Record<string, string> = {
  director: EMBER,
  character: JADE,
  writer: AURORA,
  god: CINNABAR,
  reviewer: PHOSPHOR,
  reflection: SILVER,
}

function getRoleColor(role: string): string {
  return ROLE_COLORS[role] || TEXT_SECONDARY
}

// ---------- Charts ----------
function renderChapterChart() {
  if (!chapterChartEl.value) return
  if (!chapterChart) {
    chapterChart = echarts.init(chapterChartEl.value, undefined, { renderer: 'canvas' })
  }

  const chapters = stats.value.by_chapter
  const xData = chapters.map((c) => `Ch.${c.chapter_index}`)
  const yData = chapters.map((c) => c.total_tokens)

  chapterChart.setOption({
    grid: { left: 60, right: 24, top: 24, bottom: 36 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: BORDER_RULE } },
      axisLabel: { color: TEXT_MUTED, fontFamily: 'JetBrains Mono', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: BORDER_RULE } },
      axisLabel: {
        color: TEXT_MUTED,
        fontFamily: 'JetBrains Mono',
        fontSize: 11,
        formatter: (v: number) => formatTokens(v),
      },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1c1826',
      borderColor: 'rgba(212, 121, 58, 0.45)',
      textStyle: { color: '#ede6d8', fontFamily: 'JetBrains Mono', fontSize: 12 },
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name}<br/>Token: <b>${formatNum(p.value)}</b>`
      },
    },
    series: [
      {
        type: 'bar',
        data: yData,
        itemStyle: { color: EMBER },
        emphasis: { itemStyle: { color: EMBER } },
        barMaxWidth: 32,
      },
      {
        type: 'line',
        data: yData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: EMBER, width: 2 },
        itemStyle: { color: EMBER },
        areaStyle: { color: EMBER_DIM },
      },
    ],
  })
}

function renderStackedChart() {
  if (!stackedChartEl.value) return
  if (!stackedChart) {
    stackedChart = echarts.init(stackedChartEl.value, undefined, { renderer: 'canvas' })
  }

  const raw = stats.value.by_chapter_and_role
  if (!raw.length) {
    stackedChart.clear()
    return
  }

  // Collect unique chapters & roles
  const chapterSet = new Set<number>()
  const roleSet = new Set<string>()
  for (const r of raw) {
    chapterSet.add(r.chapter_index)
    roleSet.add(r.role)
  }
  const chapters = Array.from(chapterSet).sort((a, b) => a - b)
  const roles = Array.from(roleSet)

  // Build lookup
  const lookup: Record<string, Record<number, number>> = {}
  for (const role of roles) lookup[role] = {}
  for (const r of raw) {
    lookup[r.role][r.chapter_index] = r.total_tokens
  }

  const xData = chapters.map((c) => `Ch.${c}`)
  const series = roles.map((role) => ({
    name: role,
    type: 'line' as const,
    stack: 'total',
    areaStyle: { opacity: 0.6 },
    emphasis: { focus: 'series' as const },
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 1 },
    itemStyle: { color: getRoleColor(role) },
    data: chapters.map((ch) => lookup[role][ch] || 0),
  }))

  stackedChart.setOption({
    grid: { left: 60, right: 24, top: 36, bottom: 36 },
    legend: {
      top: 0,
      textStyle: { color: TEXT_SECONDARY, fontFamily: 'Instrument Sans', fontSize: 12 },
      itemWidth: 12,
      itemHeight: 8,
    },
    xAxis: {
      type: 'category',
      data: xData,
      boundaryGap: false,
      axisLine: { lineStyle: { color: BORDER_RULE } },
      axisLabel: { color: TEXT_MUTED, fontFamily: 'JetBrains Mono', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: BORDER_RULE } },
      axisLabel: {
        color: TEXT_MUTED,
        fontFamily: 'JetBrains Mono',
        fontSize: 11,
        formatter: (v: number) => formatTokens(v),
      },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1c1826',
      borderColor: 'rgba(212, 121, 58, 0.45)',
      textStyle: { color: '#ede6d8', fontFamily: 'JetBrains Mono', fontSize: 12 },
    },
    series,
  })
}

// ---------- Data Loading ----------
async function loadStats() {
  try {
    const res = await client.get('/token-stats')
    stats.value = {
      total: res.data.total || { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      by_role: res.data.by_role || [],
      by_chapter: res.data.by_chapter || [],
      by_chapter_and_role: res.data.by_chapter_and_role || [],
    }
    await nextTick()
    renderChapterChart()
    renderStackedChart()
  } catch {
    /* ignore */
  }
}

// ---------- Resize ----------
function handleResize() {
  chapterChart?.resize()
  stackedChart?.resize()
}

// ---------- Lifecycle ----------
const unsubToken = onWSEvent('token_update', () => {
  loadStats()
})

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  unsubToken()
  window.removeEventListener('resize', handleResize)
  chapterChart?.dispose()
  stackedChart?.dispose()
})
</script>

<style scoped lang="scss">
.token-page {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: var(--sp-md);
  padding-bottom: var(--sp-lg);
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

.ledger-rule {
  border-bottom: 1px solid var(--border-rule);
}

/* ---------- Totals ---------- */
.totals-section {
  display: flex;
  gap: var(--sp-2xl);
  padding: var(--sp-xl) 0;
}

.total-item {
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
}

.total-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.total-value {
  font-size: var(--fs-2xl);
  font-weight: 600;
  color: var(--accent-ember);
  line-height: 1.2;
}

.prompt-color {
  color: var(--accent-aurora);
}

.completion-color {
  color: var(--accent-jade);
}

.text-muted {
  color: var(--text-muted);
}

/* ---------- Role Section ---------- */
.role-section {
  padding: var(--sp-xl) 0;
}

.section-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0 0 var(--sp-lg) 0;
}

.role-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}

.role-row {
  display: grid;
  grid-template-columns: 140px 1fr 120px;
  align-items: center;
  gap: var(--sp-md);
  padding: var(--sp-xs) 0;
}

.role-info {
  display: flex;
  align-items: baseline;
  gap: var(--sp-sm);
}

.role-name {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.role-pct {
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.role-bar-track {
  position: relative;
  height: 6px;
  background: var(--bg-elevated);
  overflow: hidden;
}

.role-bar-fill {
  position: absolute;
  top: 0;
  height: 100%;
  transition: width 0.3s ease-out;

  &.prompt-bar {
    left: 0;
    background: var(--accent-aurora);
    opacity: 0.85;
  }

  &.completion-bar {
    background: var(--accent-jade);
    opacity: 0.85;
  }
}

.role-nums {
  font-size: var(--fs-xs);
  display: flex;
  gap: var(--sp-2xs);
  justify-content: flex-end;
}

/* ---------- Chart Section ---------- */
.chart-section {
  padding: var(--sp-xl) 0;
}

.chart-container {
  width: 100%;
  height: 280px;
}

.chart-container--tall {
  height: 360px;
}
</style>
