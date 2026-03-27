<template>
  <div class="emotion-chart" v-loading="loading">
    <div ref="chartRef" class="chart-container" v-if="states.length"></div>
    <EmptyState v-else-if="!loading" message="暂无情感数据" icon="📈" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useCharacterStore } from '@/stores/characters'
import EmptyState from '@/components/common/EmptyState.vue'
import type { EmotionState } from '@/api/types'

const props = defineProps<{ characterId: string }>()

const characterStore = useCharacterStore()
const chartRef = ref<HTMLElement | null>(null)
const states = ref<EmotionState[]>([])
const loading = ref(false)
let chart: echarts.ECharts | null = null

const dimensions = [
  { key: 'happiness', name: '快乐', color: '#4ade80' },
  { key: 'anger', name: '愤怒', color: '#ef4444' },
  { key: 'fear', name: '恐惧', color: '#a78bfa' },
  { key: 'sadness', name: '悲伤', color: '#3b82f6' },
  { key: 'trust', name: '信任', color: '#22d3ee' },
  { key: 'surprise', name: '惊讶', color: '#fbbf24' },
]

async function loadAndRender() {
  loading.value = true
  try {
    const data = await characterStore.loadEmotions(props.characterId)
    states.value = data
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !states.value.length) return

  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value, 'dark')

  const xLabels = states.value.map((s) => `${s.chapter + 1}.${s.scene + 1}`)

  const series = dimensions.map((dim) => ({
    name: dim.name,
    type: 'line' as const,
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { color: dim.color, width: 2 },
    itemStyle: { color: dim.color },
    data: states.value.map((s) => (s as any)[dim.key]),
  }))

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e293b',
      borderColor: '#475569',
      textStyle: { color: '#e2e8f0' },
    },
    legend: {
      data: dimensions.map((d) => d.name),
      textStyle: { color: '#94a3b8' },
      bottom: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      axisLine: { lineStyle: { color: '#475569' } },
      name: '章.场景',
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      axisLabel: { color: '#94a3b8' },
      axisLine: { lineStyle: { color: '#475569' } },
      splitLine: { lineStyle: { color: '#334155' } },
    },
    series,
  })
}

onMounted(() => loadAndRender())

watch(() => props.characterId, () => loadAndRender())
</script>

<style scoped lang="scss">
.chart-container {
  width: 100%;
  height: 350px;
}
</style>
