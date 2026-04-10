<template>
  <div class="relationship-graph-wrapper">
    <!-- V10: Graph mode toggle + Path query -->
    <div class="graph-toolbar">
      <div class="toolbar-left">
        <el-segmented v-model="graphMode" :options="graphModeOptions" size="small" />
      </div>
      <div class="toolbar-right" v-if="graphMode === 'knowledge'">
        <el-input
          v-model="pathFrom"
          placeholder="角色A"
          size="small"
          style="width: 100px"
        />
        <span class="path-arrow">→</span>
        <el-input
          v-model="pathTo"
          placeholder="角色B"
          size="small"
          style="width: 100px"
        />
        <el-button size="small" type="primary" @click="queryPath" :loading="pathLoading">
          查路径
        </el-button>
        <el-button size="small" @click="clearPathHighlight" v-if="highlightedPath.length > 0">
          清除
        </el-button>
      </div>
    </div>

    <!-- History Slider (relationship mode only) -->
    <div class="graph-controls" v-if="graphMode === 'relationship' && maxChapter > 0">
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
      <template v-if="graphMode === 'relationship'">
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
      </template>
      <template v-else>
        <div class="legend-item" v-for="item in knowledgeLegend" :key="item.type">
          <span class="legend-shape" :class="item.shape" :style="{ background: item.color }"></span>
          <span class="legend-text">{{ item.label }}</span>
        </div>
      </template>
    </div>

    <div ref="graphContainer" class="relationship-graph"></div>

    <!-- Stats summary -->
    <div class="graph-stats" v-if="characterStore.characters.length > 0">
      <span class="stat-item">
        <span class="stat-num font-data">{{ graphMode === 'knowledge' ? knowledgeNodeCount : characterStore.characters.length }}</span>
        <span class="stat-label">节点</span>
      </span>
      <span class="stat-item">
        <span class="stat-num font-data">{{ graphMode === 'knowledge' ? knowledgeEdgeCount : currentEdges.length }}</span>
        <span class="stat-label">关系</span>
      </span>
      <span class="stat-item" v-if="graphMode === 'relationship' && avgTrust !== null">
        <span class="stat-num font-data">{{ avgTrust.toFixed(1) }}</span>
        <span class="stat-label">平均信任</span>
      </span>
      <span class="stat-item" v-if="highlightedPath.length > 0">
        <span class="stat-num font-data" style="color: var(--accent-jade)">{{ highlightedPath.length }}</span>
        <span class="stat-label">路径长度</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useCharacterStore } from '@/stores/characters'
import { useProgressStore } from '@/stores/progress'
import { onWSEvent } from '@/composables/useWebSocket'
import { fetchGraphPath } from '@/api/story'
import client from '@/api/client'
import { Network, DataSet } from 'vis-network/standalone'
import { ElMessage } from 'element-plus'

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

// V10: Graph mode toggle
const graphMode = ref<string>('relationship')
const graphModeOptions = [
  { label: '关系图', value: 'relationship' },
  { label: '知识图谱', value: 'knowledge' },
]

// V10: Path query
const pathFrom = ref('')
const pathTo = ref('')
const pathLoading = ref(false)
const highlightedPath = ref<string[]>([])

// V10: Knowledge graph stats
const knowledgeNodeCount = ref(0)
const knowledgeEdgeCount = ref(0)

// V10: Knowledge graph legend
const knowledgeLegend = [
  { type: 'character', label: '角色', color: '#d4793a', shape: 'shape-dot' },
  { type: 'location', label: '地点', color: '#58a6ff', shape: 'shape-diamond' },
  { type: 'faction', label: '势力', color: '#4ec994', shape: 'shape-square' },
  { type: 'event', label: '事件', color: '#fbbf24', shape: 'shape-triangle' },
]

// V10: Node type → vis-network config
const nodeTypeConfig: Record<string, { shape: string; color: string; size: number }> = {
  character: { shape: 'dot', color: '#d4793a', size: 22 },
  location: { shape: 'diamond', color: '#58a6ff', size: 18 },
  faction: { shape: 'square', color: '#4ec994', size: 18 },
  event: { shape: 'triangle', color: '#fbbf24', size: 16 },
}

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

// ---- Relationship mode graph (original) ----
function buildRelationshipGraph() {
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

// ---- V10: Knowledge graph mode (Neo4j) ----
async function buildKnowledgeGraph() {
  if (!graphContainer.value) return

  await characterStore.loadGraphData()
  const gd = characterStore.graphData
  if (!gd || !gd.nodes || gd.nodes.length === 0) {
    // Fallback to relationship graph if no Neo4j data
    buildRelationshipGraph()
    return
  }

  knowledgeNodeCount.value = gd.nodes.length
  knowledgeEdgeCount.value = gd.edges.length

  const nodes = new DataSet(
    gd.nodes.map((n: any) => {
      const cfg = nodeTypeConfig[n.type] || nodeTypeConfig.character
      const isHighlighted = highlightedPath.value.includes(n.id)
      return {
        id: n.id,
        label: n.label || n.id,
        title: `[${n.type}] ${n.label}\n${JSON.stringify(n.properties || {}).slice(0, 100)}`,
        shape: cfg.shape,
        size: isHighlighted ? cfg.size * 1.5 : cfg.size,
        color: {
          background: isHighlighted ? '#fbbf24' : cfg.color,
          border: isHighlighted ? '#f59e0b' : cfg.color,
          highlight: { background: cfg.color, border: '#e6edf3' },
          hover: { background: cfg.color, border: '#e6edf3' },
        },
        font: {
          color: '#e6edf3',
          size: n.type === 'character' ? 14 : 11,
          face: 'Inter, PingFang SC, sans-serif',
          strokeWidth: 2,
          strokeColor: '#0d1117',
        },
        borderWidth: isHighlighted ? 4 : 2,
        shadow: {
          enabled: true,
          color: (isHighlighted ? '#fbbf24' : cfg.color) + '40',
          size: 10,
          x: 0,
          y: 0,
        },
      }
    })
  )

  const edgeData = new DataSet(
    gd.edges.map((e: any, i: number) => {
      const isOnPath = highlightedPath.value.includes(e.from) && highlightedPath.value.includes(e.to)
      return {
        id: `e_${i}`,
        from: e.from,
        to: e.to,
        label: e.label || '',
        color: {
          color: isOnPath ? 'rgba(251, 191, 36, 0.9)' : 'rgba(158, 143, 163, 0.4)',
          highlight: '#fbbf24',
          hover: '#c8bfd4',
        },
        width: isOnPath ? 4 : 1.5,
        dashes: !isOnPath,
        arrows: { to: { enabled: true, scaleFactor: 0.5 } },
        font: {
          color: '#8b949e',
          size: 10,
          face: 'Inter, PingFang SC, sans-serif',
          strokeWidth: 0,
          background: '#161b22',
        },
        smooth: { enabled: true, type: 'curvedCW', roundness: 0.12 },
      }
    })
  )

  const options = {
    physics: {
      stabilization: { iterations: 200, fit: true },
      barnesHut: {
        gravitationalConstant: -3000,
        centralGravity: 0.2,
        springLength: 200,
        springConstant: 0.03,
        damping: 0.1,
      },
    },
    interaction: { hover: true, zoomView: true, dragNodes: true, tooltipDelay: 200 },
    layout: { improvedLayout: true, randomSeed: 42 },
  }

  if (network) network.destroy()
  network = new Network(graphContainer.value, { nodes, edges: edgeData }, options)

  network.on('click', (params: any) => {
    if (params.nodes.length > 0) {
      emit('node-click', params.nodes[0])
    }
  })
}

// ---- V10: Path query ----
async function queryPath() {
  if (!pathFrom.value || !pathTo.value) {
    ElMessage.warning('请输入两个角色ID或名称')
    return
  }
  pathLoading.value = true
  try {
    const res = await fetchGraphPath(pathFrom.value, pathTo.value)
    if (res.paths && res.paths.length > 0) {
      const path = res.paths[0]
      highlightedPath.value = (path.nodes || []).map((n: any) => n.id || n.character_id || '')
      ElMessage.success(`找到路径，长度 ${path.edges?.length || 0}`)
      buildKnowledgeGraph()
    } else {
      ElMessage.info('未找到连接路径')
      highlightedPath.value = []
    }
  } catch {
    ElMessage.error('路径查询失败')
  } finally {
    pathLoading.value = false
  }
}

function clearPathHighlight() {
  highlightedPath.value = []
  buildKnowledgeGraph()
}

// ---- Unified build dispatch ----
function buildGraph() {
  if (graphMode.value === 'knowledge') {
    buildKnowledgeGraph()
  } else {
    buildRelationshipGraph()
  }
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
    if (!useHistory.value && graphMode.value === 'relationship') buildGraph()
  },
  { deep: true }
)

// Rebuild when graph mode changes
watch(graphMode, () => {
  highlightedPath.value = []
  buildGraph()
})

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

.graph-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  padding: var(--sp-xs) 0;
  flex-wrap: wrap;
}

.toolbar-left {
  flex-shrink: 0;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--sp-xs);
}

.path-arrow {
  font-size: var(--fs-sm);
  color: var(--text-muted);
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

.legend-shape {
  width: 10px;
  height: 10px;
  flex-shrink: 0;

  &.shape-dot { border-radius: 50%; }
  &.shape-diamond { transform: rotate(45deg); border-radius: 2px; }
  &.shape-square { border-radius: 2px; }
  &.shape-triangle {
    width: 0;
    height: 0;
    background: transparent !important;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 10px solid #fbbf24;
  }
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
