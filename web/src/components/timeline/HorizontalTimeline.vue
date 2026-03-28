<template>
  <div class="vertical-timeline" v-if="totalChapters > 0">
    <div class="timeline-track">
      <!-- Chapter nodes -->
      <div
        v-for="ch in totalChapters"
        :key="ch"
        class="chapter-node"
        :class="{ current: ch <= completedChapters }"
      >
        <div class="node-marker">
          <div class="marker-dot" :class="{ completed: ch <= completedChapters }"></div>
          <div class="marker-line" v-if="ch < totalChapters"></div>
        </div>
        <div class="node-content">
          <div class="node-header">
            <span class="chapter-label">第{{ ch }}章</span>
            <span class="chapter-status font-data" v-if="ch <= completedChapters">已完成</span>
          </div>
          <!-- Events for this chapter -->
          <div class="node-events" v-if="eventsForChapter(ch).length > 0">
            <div
              v-for="(evt, i) in eventsForChapter(ch)"
              :key="i"
              class="event-item"
              :class="evt.kind"
            >
              <span class="event-dot"></span>
              <span class="event-title">{{ evt.title }}</span>
              <span class="event-type font-data">{{ evt.kind === 'decision' ? '命运裁决' : evt.eventType || '事件' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TimelineEvent, GodDecision } from '@/api/types'

const props = defineProps<{
  events: TimelineEvent[]
  decisions: GodDecision[]
  totalChapters: number
  completedChapters: number
}>()

interface EventNode {
  chapter: number
  title: string
  description: string
  kind: 'event' | 'decision'
  eventType?: string
}

const allNodes = computed<EventNode[]>(() => {
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

function eventsForChapter(ch: number): EventNode[] {
  return allNodes.value.filter(n => n.chapter === ch)
}
</script>

<style scoped lang="scss">
.vertical-timeline {
  padding: var(--sp-sm) 0;
}

.timeline-track {
  display: flex;
  flex-direction: column;
}

.chapter-node {
  display: flex;
  gap: var(--sp-md);
  min-height: 48px;
}

.node-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 20px;
}

.marker-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--border-default);
  border: 2px solid var(--bg-void);
  flex-shrink: 0;
  z-index: 1;

  &.completed {
    background: var(--accent-jade);
  }
}

.marker-line {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: var(--border-default);
}

.node-content {
  flex: 1;
  padding-bottom: var(--sp-md);
  min-width: 0;
}

.node-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-xs);
}

.chapter-label {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.chapter-status {
  font-size: var(--fs-xs);
  color: var(--accent-jade);
}

.node-events {
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
  margin-top: var(--sp-xs);
}

.event-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-xs) 0;
  font-size: var(--fs-xs);
}

.event-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-jade);
  flex-shrink: 0;
}

.event-item.decision .event-dot {
  background: var(--accent-ember);
  width: 8px;
  height: 8px;
}

.event-title {
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-type {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}
</style>
