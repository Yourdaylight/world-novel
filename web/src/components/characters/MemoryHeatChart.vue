<template>
  <div class="memory-heat-chart" v-loading="loading">
    <div class="chart-row">
      <div ref="pieRef" class="chart-pie" v-if="hasData"></div>
      <div class="heat-legend" v-if="hasData">
        <div v-for="item in legendItems" :key="item.label" class="legend-row">
          <span class="legend-dot" :style="{ background: item.color }"></span>
          <span class="legend-label">{{ item.label }}</span>
          <span class="legend-count font-data">{{ item.count }}</span>
        </div>
      </div>
    </div>
    <EmptyState v-if="!loading && !hasData" message="暂无记忆热度数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import EmptyState from '@/components/common/EmptyState.vue'
import { fetchMemoryHeat } from '@/api/memory'
import type { MemoryHeatStats } from '@/api/types'

const props = defineProps<{ characterId: string }>()
const emit = defineEmits<{ 'loaded': [stats: MemoryHeatStats] }>()

const pieRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const stats = ref<MemoryHeatStats | null>(null)
let chart: echarts.ECharts | null = null

const hasData = computed(() => stats.value && stats.value.total_active > 0)

const colors = {
  hot: '#e04545',
  warm: '#d4793a',
  cold: '#58a6ff',
  frozen: '#a67fd4',
}

const legendItems = computed(() => {
  if (!stats.value) return []
  return [
    { label: '鲜活 (Hot)', color: colors.hot, count: stats.value.hot_count },
    { label: '温热 (Warm)', color: colors.warm, count: stats.value.warm_count },
    { label: '冷却 (Cold)', color: colors.cold, count: stats.value.cold_count },
    { label: '永恒 (Frozen)', color: colors.frozen, count: stats.value.frozen_count },
  ]
})

async function loadAndRender() {
  loading.value = true
  try {
    const data = await fetchMemoryHeat(props.characterId)
    stats.value = data.stats || null
    if (stats.value) emit('loaded', stats.value)
    await nextTick()
    renderPie()
  } finally {
    loading.value = false
  }
}

function renderPie() {
  if (!pieRef.value || !stats.value) return
  if (chart) chart.dispose()
  chart = echarts.init(pieRef.value, 'dark')

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1e293b',
      borderColor: '#475569',
      textStyle: { color: '#e2e8f0' },
    },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
      },
      data: [
        { value: stats.value.hot_count, name: '鲜活', itemStyle: { color: colors.hot } },
        { value: stats.value.warm_count, name: '温热', itemStyle: { color: colors.warm } },
        { value: stats.value.cold_count, name: '冷却', itemStyle: { color: colors.cold } },
        { value: stats.value.frozen_count, name: '永恒', itemStyle: { color: colors.frozen } },
      ],
    }],
  })
}

onMounted(() => loadAndRender())
watch(() => props.characterId, () => loadAndRender())
</script>

<style scoped lang="scss">
.memory-heat-chart {
  min-height: 160px;
}
.chart-row {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
}
.chart-pie {
  width: 160px;
  height: 160px;
  flex-shrink: 0;
}
.heat-legend {
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
}
.legend-row {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.legend-label {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  min-width: 7rem;
}
.legend-count {
  font-size: var(--fs-sm);
  color: var(--text-primary);
  font-weight: 600;
}
</style>
