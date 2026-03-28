<template>
  <div class="horizontal-timeline" v-if="totalChapters > 0">
    <div class="timeline-scroll" ref="scrollContainer">
      <div class="timeline-track" :style="{ width: trackWidth + 'px' }">
        <div class="axis-line"></div>

        <div
          v-for="ch in totalChapters"
          :key="ch"
          class="chapter-marker"
          :class="{ current: ch <= completedChapters, active: ch === activeChapter }"
          :style="{ left: markerLeft(ch) + 'px' }"
          @click="$emit('select-chapter', ch)"
        >
          <div class="marker-dot"></div>
          <span class="marker-label">{{ ch }}</span>
        </div>

        <div
          v-for="(node, i) in eventNodes"
          :key="'evt-' + i"
          class="event-node"
          :class="node.kind"
          :style="{ left: markerLeft(node.chapter) + 'px' }"
          @mouseenter="hoveredNode = node"
          @mouseleave="hoveredNode = null"
          @click="$emit('select-event', node)"
        >
          <div class="node-dot"></div>
          <span class="node-label">{{ node.title.substring(0, 8) }}</span>
        </div>
      </div>
    </div>

    <div class="timeline-tooltip" v-if="hoveredNode">
      <strong>{{ hoveredNode.title }}</strong>
      <span class="tooltip-meta">第{{ hoveredNode.chapter }}章 · {{ hoveredNode.kind === 'decision' ? '命运裁决' : hoveredNode.eventType || '事件' }}</span>
      <p v-if="hoveredNode.description">{{ hoveredNode.description.substring(0, 120) }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TimelineEvent, GodDecision } from '@/api/types'

const props = defineProps<{
  events: TimelineEvent[]
  decisions: GodDecision[]
  totalChapters: number
  completedChapters: number
}>()

defineEmits<{
  'select-chapter': [chapter: number]
  'select-event': [node: EventNode]
}>()

interface EventNode {
  chapter: number
  title: string
  description: string
  kind: 'event' | 'decision'
  eventType?: string
}

const hoveredNode = ref<EventNode | null>(null)
const scrollContainer = ref<HTMLElement | null>(null)
const activeChapter = ref(0)

const MARKER_GAP = 100
const MARGIN = 40

const trackWidth = computed(() => MARGIN * 2 + props.totalChapters * MARKER_GAP)

function markerLeft(chapter: number): number {
  return MARGIN + (chapter - 1) * MARKER_GAP
}

const eventNodes = computed<EventNode[]>(() => {
  const nodes: EventNode[] = []

  for (const e of props.events) {
    nodes.push({
      chapter: (e.chapter_index ?? 0) + 1,
      title: e.title,
      description: e.description,
      kind: 'event',
      eventType: e.event_type,
    })
  }

  for (const d of props.decisions) {
    const events = (d as any).world_events || []
    const title = events.length > 0 ? events.map((e: any) => e.title || '').join(', ') : '命运裁决'
    nodes.push({
      chapter: (d.chapter_index ?? 0) + 1,
      title: title,
      description: (d as any).next_chapter_guidance || d.description || '',
      kind: 'decision',
    })
  }

  return nodes.sort((a, b) => a.chapter - b.chapter)
})
</script>

<style scoped lang="scss">
.horizontal-timeline {
  position: relative;
  margin-bottom: var(--sp-lg);
}

.timeline-scroll {
  overflow-x: auto;
  padding: var(--sp-lg) 0 var(--sp-2xl) 0;
}

.timeline-track {
  position: relative;
  height: 80px;
  min-width: 100%;
}

.axis-line {
  position: absolute;
  top: 20px;
  left: 30px;
  right: 30px;
  height: 2px;
  background: var(--border-default);
}

.chapter-marker {
  position: absolute;
  top: 12px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;

  .marker-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--border-default);
    border: 2px solid var(--bg-void);
    z-index: 1;
  }

  .marker-label {
    font-family: var(--font-data);
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  &.current .marker-dot {
    background: var(--accent-jade);
  }

  &.active .marker-dot {
    background: var(--accent-ember);
    box-shadow: 0 0 8px rgba(212, 121, 58, 0.4);
  }
}

.event-node {
  position: absolute;
  top: 42px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;

  .node-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-jade);
  }

  .node-label {
    font-family: var(--font-ui);
    font-size: 9px;
    color: var(--text-muted);
    margin-top: 2px;
    white-space: nowrap;
    max-width: 60px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &.decision .node-dot {
    width: 12px;
    height: 12px;
    background: var(--accent-ember);
  }

  &:hover .node-dot {
    transform: scale(1.4);
  }
}

.timeline-tooltip {
  position: absolute;
  bottom: 0;
  left: var(--sp-md);
  right: var(--sp-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--sp-sm) var(--sp-md);
  z-index: 10;

  strong {
    display: block;
    font-size: var(--fs-sm);
    color: var(--text-primary);
    margin-bottom: 2px;
  }

  .tooltip-meta {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    display: block;
    margin-bottom: 4px;
  }

  p {
    font-size: var(--fs-xs);
    color: var(--text-secondary);
    line-height: 1.4;
    margin: 0;
  }
}
</style>
