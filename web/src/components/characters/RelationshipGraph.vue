<template>
  <div class="relationship-graph-wrapper">
    <!-- History Slider -->
    <div class="graph-controls" v-if="maxChapter > 0">
      <span class="control-label">第{{ sliderChapter + 1 }}章关系快照</span>
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
      <el-button size="small" @click="togglePlayback" :type="isPlaying ? 'danger' : 'primary'">
        {{ isPlaying ? '停止' : '演进' }}
      </el-button>
      <el-button size="small" @click="resetToLatest">最新</el-button>
    </div>

    <!-- Legend -->
    <div class="graph-legend" v-if="characterStore.characters.length > 0">
      <div class="legend-item" v-for="(color, role) in rolePalette" :key="role">
        <span class="legend-dot" :style="{ background: color }"></span>
        <span class="legend-text">{{ roleLabels[role] || role }}</span>
      </div>
      <div class="legend-sep"></div>
      <div class="legend-item">
        <span class="legend-line solid"></span>
        <span class="legend-text">正面关系</span>
      </div>
      <div class="legend-item">
        <span class="legend-line dashed"></span>
        <span class="legend-text">负面关系</span>
      </div>
    </div>

    <div ref="graphContainer" class="relationship-graph"></div>

    <!-- Stats summary -->
    <div class="graph-stats" v-if="characterStore.characters.length > 0">
      <span class="stat-item">
        <span class="stat-num font-data">{{ characterStore.characters.length }}</span>
        <span class="stat-label">角色</span>
      </span>
      <span class="stat-item">
        <span class="stat-num font-data">{{ currentEdges.length }}</span>
        <span class="stat-label">关系</span>
      </span>
      <span class="stat-item" v-if="avgTrust !== null">
        <span class="stat-num font-data">{{ avgTrust.toFixed(1) }}</span>
        <span class="stat-label">平均信任</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useCharacterStore } from '@/stores/characters'
import { useProgressStore } from '@/stores/progress'
import { onWSEvent } from '@/composables/useWebSocket'
import client from '@/api/client'
import { Network, DataSet } from 'vis-network/standalone'

const emit = defineEmits<{
  'node-click': [characterId: string]
}>()

const graphContainer = ref<HTMLElement | null>(null)
const characterStore = useCharacterStore()
let network: Network | null = null

const maxChapter = ref(0)
const sliderChapter = ref(0)
const historyEdges = ref<any[]>([])
const useHistory = ref(false)
const isPlaying = ref(false)
let playTimer: ReturnType<typeof setInterval> | null = null

// Role-based color palette
const rolePalette: Record<string, string> = {
  protagonist: '#d4793a',
  antagonist: '#e04545',
  supporting: '#a67fd4',
  mentor: '#4ec994',
  love_interest: '#c8bfd4',
  default: '#9e8fa3',
}

const roleLabels: Record<string, string> = {
  protagonist: '主角',
  antagonist: '反派',
  supporting: '配角',
  mentor: '导师',
  love_interest: '情感线',
  default: '其他',
}

function getRoleColor(role: string): string {
  const normalized = role.toLowerCase().replace(/\s+/g, '_')
  return rolePalette[normalized] || rolePalette.default
}

function getEdgeColor(edge: any): { color: string; highlight: string; dashes: boolean } {
  const trust = edge.trust ?? 0
  const affection = edge.affection ?? 0
  const sentiment = trust + affection

  if (sentiment > 5) {
    return { color: 'rgba(78, 201, 148, 0.6)', highlight: '#4ec994', dashes: false }
  } else if (sentiment > 0) {
    return { color: 'rgba(200, 191, 212, 0.5)', highlight: '#c8bfd4', dashes: false }
  } else if (sentiment > -5) {
    return { color: 'rgba(158, 143, 163, 0.4)', highlight: '#9e8fa3', dashes: true }
  } else {
    return { color: 'rgba(224, 69, 69, 0.5)', highlight: '#e04545', dashes: true }
  }
}

const currentEdges = computed(() => {
  return useHistory.value ? historyEdges.value : characterStore.edges
})

const avgTrust = computed(() => {
  const edges = currentEdges.value
  if (!edges.length) return null
  const sum = edges.reduce((acc: number, e: any) => acc + (e.trust ?? 0), 0)
  return sum / edges.length
})

function formatSliderTooltip(val: number) {
  return `第${val + 1}章`
}

function buildGraph() {
  if (!graphContainer.value) return

  const chars = characterStore.characters
  const edges = currentEdges.value

  if (!chars.length) return

  const nodes = new DataSet(
    chars.map((c) => {
      const roleColor = getRoleColor(c.role)
      return {
        id: c.id,
        label: c.name,
        title: `${c.name}\n${roleLabels[c.role.toLowerCase().replace(/\s+/g, '_')] || c.role}`,
        color: {
          background: roleColor,
          border: roleColor,
          highlight: { background: roleColor, border: '#e6edf3' },
          hover: { background: roleColor, border: '#e6edf3' },
        },
        font: {
          color: '#e6edf3',
          size: 14,
          face: 'Inter, PingFang SC, sans-serif',
          strokeWidth: 2,
          strokeColor: '#0d1117',
        },
        size: c.role.toLowerCase().includes('protagonist') ? 28 : 20,
        shape: 'dot',
        borderWidth: 2,
        borderWidthSelected: 3,
        shadow: {
          enabled: true,
          color: roleColor + '40',
          size: 12,
          x: 0,
          y: 0,
        },
      }
    })
  )

  const edgeData = new DataSet(
    edges.map((e: any, i: number) => {
      const edgeStyle = getEdgeColor(e)
      const trust = e.trust ?? 0
      const affection = e.affection ?? 0
      return {
        id: i,
        from: e.from || e.source_id,
        to: e.to || e.target_id,
        label: e.label || e.relationship_type || '',
        color: { color: edgeStyle.color, highlight: edgeStyle.highlight, hover: edgeStyle.highlight },
        font: {
          color: '#8b949e',
          size: 11,
          face: 'Inter, PingFang SC, sans-serif',
          strokeWidth: 0,
          background: '#161b22',
          align: 'middle',
        },
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
        width: Math.max(1.5, Math.abs(trust + affection) / 3),
        dashes: edgeStyle.dashes,
        smooth: { enabled: true, type: 'curvedCW', roundness: 0.15 },
        title: `信任: ${trust} / 情感: ${affection}`,
      }
    })
  )

  const options = {
    physics: {
      stabilization: { iterations: 150, fit: true },
      barnesHut: {
        gravitationalConstant: -4000,
        centralGravity: 0.3,
        springLength: 160,
        springConstant: 0.04,
        damping: 0.09,
      },
    },
    interaction: {
      hover: true,
      zoomView: true,
      dragNodes: true,
      tooltipDelay: 200,
    },
    layout: {
      improvedLayout: true,
      randomSeed: 42,
    },
    nodes: {
      shape: 'dot',
      scaling: { min: 16, max: 32 },
    },
    edges: {
      smooth: { enabled: true, type: 'curvedCW', roundness: 0.15 },
    },
  }

  if (network) network.destroy()
  network = new Network(graphContainer.value, { nodes, edges: edgeData }, options)

  network.on('click', (params: any) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      emit('node-click', nodeId)
    }
  })
}

async function loadHistoryForChapter(chapter: number) {
  try {
    const res = await client.get('/relationship-history', { params: { chapter_index: chapter } })
    historyEdges.value = res.data.history || []
    useHistory.value = true
    buildGraph()
  } catch {
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

function togglePlayback() {
  if (isPlaying.value) {
    stopPlayback()
  } else {
    startPlayback()
  }
}

function startPlayback() {
  isPlaying.value = true
  sliderChapter.value = 0
  loadHistoryForChapter(0)

  playTimer = setInterval(() => {
    if (sliderChapter.value >= maxChapter.value) {
      stopPlayback()
      return
    }
    sliderChapter.value++
    loadHistoryForChapter(sliderChapter.value)
  }, 1500)
}

function stopPlayback() {
  isPlaying.value = false
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

onMounted(() => {
  buildGraph()
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
onUnmounted(() => {
  unsub()
  stopPlayback()
})
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
}

.graph-legend {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  padding: var(--sp-xs) 0;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-line {
  width: 16px;
  height: 0;
  border-top: 2px solid var(--accent-jade);
  flex-shrink: 0;

  &.dashed {
    border-top-style: dashed;
    border-top-color: var(--accent-cinnabar);
  }
}

.legend-sep {
  width: 1px;
  height: 12px;
  background: var(--border-rule);
}

.legend-text {
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--text-muted);
}

.relationship-graph {
  width: 100%;
  min-height: 400px;
  height: calc(100vh - 280px);
  max-height: 800px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}

.graph-stats {
  display: flex;
  gap: var(--sp-lg);
  padding: var(--sp-sm) 0;
}

.stat-item {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-num {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--accent-ember);
}

.stat-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}
</style>
