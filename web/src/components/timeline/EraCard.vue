<template>
  <div class="era-card">
    <div class="era-header">
      <span class="era-name">{{ era.name }}</span>
      <span class="era-time" v-if="era.story_time_start || era.story_time_end">
        {{ era.story_time_start || '?' }} — {{ era.story_time_end || '?' }}
      </span>
      <span class="era-range">章节 {{ (era.chapter_start || 0) + 1 }} — {{ (era.chapter_end || 0) + 1 }}</span>
    </div>
    <p class="era-desc" v-if="era.description">{{ era.description }}</p>

    <!-- Vertical timeline -->
    <div class="timeline-track" v-if="events.length || (decisions && decisions.length)">
      <div v-for="item in mergedItems" :key="item.id" class="timeline-item" :class="item.kind">
        <div class="timeline-dot" :class="item.kind"></div>
        <div class="timeline-content">
          <div class="timeline-time">
            <span v-if="item.story_time" class="story-time font-data">{{ item.story_time }}</span>
            <span class="chapter-ref font-data">第{{ item.chapter_index + 1 }}章</span>
          </div>
          <!-- Event -->
          <template v-if="item.kind === 'event'">
            <div class="item-header">
              <el-tag size="small" type="info">{{ item.event_type }}</el-tag>
              <span class="item-title">{{ item.title }}</span>
            </div>
            <p class="item-desc" v-if="item.description">{{ item.description }}</p>
            <div class="item-tags" v-if="item.affected_characters?.length">
              <el-tag v-for="c in item.affected_characters" :key="c" size="small">{{ c }}</el-tag>
            </div>
          </template>
          <!-- God Decision -->
          <template v-else>
            <div class="item-header">
              <el-tag size="small" type="warning">🔮 命运决策</el-tag>
              <span class="item-title">{{ item.title }}</span>
            </div>
            <p class="item-desc" v-if="item.description">{{ item.description }}</p>
          </template>
        </div>
      </div>
    </div>
    <div v-else class="no-events">暂无事件</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  era: any
  events: any[]
  decisions?: any[]
}>()

interface MergedItem {
  id: string
  kind: 'event' | 'decision'
  chapter_index: number
  story_time: string
  title: string
  description: string
  event_type?: string
  affected_characters?: string[]
}

const mergedItems = computed<MergedItem[]>(() => {
  const items: MergedItem[] = []

  for (const evt of props.events) {
    items.push({
      id: evt.event_id,
      kind: 'event',
      chapter_index: evt.chapter_index ?? 0,
      story_time: evt.story_time || '',
      title: evt.title,
      description: evt.description || '',
      event_type: evt.event_type,
      affected_characters: evt.affected_characters,
    })
  }

  for (const d of (props.decisions ?? [])) {
    // Extract summary from god decision JSON
    const dJson = typeof d.decision_json === 'string' ? JSON.parse(d.decision_json || '{}') : (d.decision_json || d)
    const guidance = dJson.next_chapter_guidance || d.next_chapter_guidance || ''
    const events = dJson.world_events || d.world_events || []
    const title = events.length ? events.map((e: any) => e.title).join(', ') : '命运介入'

    items.push({
      id: d.decision_id,
      kind: 'decision',
      chapter_index: d.chapter_index ?? 0,
      story_time: '',
      title,
      description: guidance,
    })
  }

  // Sort by story_time first, fallback chapter_index
  items.sort((a, b) => {
    if (a.story_time && b.story_time && a.story_time !== b.story_time) {
      return a.story_time.localeCompare(b.story_time)
    }
    return a.chapter_index - b.chapter_index
  })

  return items
})
</script>

<style scoped lang="scss">
.era-card {
  margin-bottom: var(--sp-lg);
  padding: var(--sp-md);
  border: 1px solid var(--border-rule);
  border-radius: 8px;
  background: var(--bg-surface);
}

.era-header {
  display: flex;
  align-items: baseline;
  gap: var(--sp-md);
  margin-bottom: var(--sp-sm);
  flex-wrap: wrap;
}

.era-name {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.era-time {
  font-family: var(--font-data);
  font-size: var(--fs-sm);
  color: var(--accent-ember);
}

.era-range {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.era-desc {
  color: var(--text-secondary);
  margin-bottom: var(--sp-md);
  line-height: 1.7;
  font-size: var(--fs-sm);
}

/* Vertical timeline track */
.timeline-track {
  position: relative;
  padding-left: 24px;

  &::before {
    content: '';
    position: absolute;
    left: 7px;
    top: 4px;
    bottom: 4px;
    width: 2px;
    background: var(--border-rule);
    border-radius: 1px;
  }
}

.timeline-item {
  position: relative;
  margin-bottom: var(--sp-md);
  padding-bottom: var(--sp-sm);

  &:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
  }
}

.timeline-dot {
  position: absolute;
  left: -20px;
  top: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--border-rule);
  background: var(--bg-surface);

  &.event {
    border-color: var(--accent-jade);
    background: var(--accent-jade);
  }
  &.decision {
    border-color: var(--accent-ember);
    background: var(--accent-ember);
  }
}

.timeline-content {
  min-height: 20px;
}

.timeline-time {
  display: flex;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-2xs);
  font-size: var(--fs-xs);

  .story-time {
    color: var(--accent-ember);
    font-weight: 600;
  }
  .chapter-ref {
    color: var(--text-muted);
  }
}

.item-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-2xs);
}

.item-title {
  font-weight: 500;
  font-size: var(--fs-sm);
  color: var(--text-primary);
}

.item-desc {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  line-height: 1.5;
  margin: 0;
}

.item-tags {
  margin-top: var(--sp-xs);
  display: flex;
  gap: var(--sp-2xs);
  flex-wrap: wrap;
}

.no-events {
  color: var(--text-muted);
  font-size: var(--fs-xs);
}
</style>
