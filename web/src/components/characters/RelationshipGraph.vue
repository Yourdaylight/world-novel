<template>
  <div class="relationship-graph-wrapper">
    <!-- History Slider -->
    <div class="graph-controls" v-if="maxChapter > 0">
      <span class="control-label">章节快照:</span>
      <el-slider
        v-model="sliderChapter"
        :min="0"
        :max="maxChapter"
        :step="1"
        :format-tooltip="formatSliderTooltip"
        size="small"
        style="flex: 1; margin: 0 12px;"
        @change="onSliderChange"
      />
      <span class="control-value font-data">第{{ sliderChapter + 1 }}章</span>
      <el-button size="small" @click="resetToLatest">最新</el-button>
    </div>
    <div ref="graphContainer" class="relationship-graph"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useCharacterStore } from '@/stores/characters'
import { useProgressStore } from '@/stores/progress'
import { onWSEvent } from '@/composables/useWebSocket'
import client from '@/api/client'
import { Network, DataSet } from 'vis-network/standalone'

const graphContainer = ref<HTMLElement | null>(null)
const characterStore = useCharacterStore()
let network: Network | null = null

const maxChapter = ref(0)
const sliderChapter = ref(0)
const historyEdges = ref<any[]>([])
const useHistory = ref(false)

function formatSliderTooltip(val: number) {
  return `第${val + 1}章`
}

function buildGraph() {
  if (!graphContainer.value) return

  const chars = characterStore.characters
  const edges = useHistory.value ? historyEdges.value : characterStore.edges

  if (!chars.length) return

  const nodes = new DataSet(
    chars.map((c) => ({
      id: c.id,
      label: c.name,
      color: {
        background: '#3b82f6',
        border: '#60a5fa',
        highlight: { background: '#2563eb', border: '#93bbfc' },
      },
      font: { color: '#e2e8f0', size: 14 },
    }))
  )

  const edgeData = new DataSet(
    edges.map((e: any, i: number) => ({
      id: i,
      from: e.from || e.source_id,
      to: e.to || e.target_id,
      label: e.label || e.relationship_type || '',
      color: { color: '#475569', highlight: '#94a3b8' },
      font: { color: '#94a3b8', size: 11, strokeWidth: 0 },
      arrows: 'to',
      width: Math.max(1, ((e.trust || 0) + (e.affection || 0)) / 2),
    }))
  )

  const options = {
    physics: { stabilization: { iterations: 100 }, barnesHut: { gravitationalConstant: -3000 } },
    interaction: { hover: true, zoomView: true },
    layout: { improvedLayout: true },
  }

  if (network) network.destroy()
  network = new Network(graphContainer.value, { nodes, edges: edgeData }, options)
}

async function loadHistoryForChapter(chapter: number) {
  try {
    const res = await client.get('/relationship-history', { params: { chapter_index: chapter } })
    historyEdges.value = res.data.history || []
    useHistory.value = true
    buildGraph()
  } catch {
    // fallback to current
    useHistory.value = false
    buildGraph()
  }
}

function onSliderChange(val: number | number[]) {
  const chapter = Array.isArray(val) ? val[0] : val
  loadHistoryForChapter(chapter)
}

function resetToLatest() {
  useHistory.value = false
  sliderChapter.value = maxChapter.value
  buildGraph()
}

onMounted(() => {
  buildGraph()
  // Estimate max chapter from progress store
  try {
    const progressStore = useProgressStore()
    if (progressStore.completed > 0) {
      maxChapter.value = progressStore.completed - 1
      sliderChapter.value = maxChapter.value
    }
  } catch { /* ignore */ }
})

watch(
  () => [characterStore.characters, characterStore.edges],
  () => {
    if (!useHistory.value) buildGraph()
  },
  { deep: true }
)

// Auto-refresh on WS relationships_updated
const unsub = onWSEvent('relationships_updated', () => {
  characterStore.loadCharacters()
})
onUnmounted(() => unsub())
</script>

<style scoped lang="scss">
.relationship-graph-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}

.graph-controls {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-sm) 0;

  .control-label {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    white-space: nowrap;
  }
  .control-value {
    font-size: var(--fs-xs);
    color: var(--text-secondary);
    white-space: nowrap;
  }
}

.relationship-graph {
  width: 100%;
  height: 450px;
  background: var(--bg-surface);
  border: 1px solid var(--border-rule);
  border-radius: 8px;
}
</style>
