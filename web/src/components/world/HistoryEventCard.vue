<template>
  <PanelCard title="历史事件" icon="📜">
    <template v-if="events.length">
      <div v-for="(evt, i) in events" :key="i" class="event-item">
        <div class="evt-header">
          <span class="evt-name">{{ evt.name || evt.title || '未命名事件' }}</span>
          <el-tag v-if="evt.era" size="small" type="info">{{ evt.era }}</el-tag>
        </div>
        <p v-if="evt.description" class="evt-desc">{{ evt.description }}</p>
        <p v-if="evt.impact" class="evt-impact">💥 {{ evt.impact }}</p>
      </div>
    </template>
    <EmptyState v-else message="暂无历史事件" icon="📜" />
  </PanelCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PanelCard from '@/components/common/PanelCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { WorldData } from '@/api/types'

const props = defineProps<{ world: WorldData }>()

const events = computed(() => {
  // Support both history (array) and history_events (array)
  const w = props.world
  if (Array.isArray(w.history) && w.history.length) return w.history
  if (Array.isArray(w.history_events) && w.history_events.length) return w.history_events
  return []
})
</script>

<style scoped lang="scss">
.event-item {
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-rule);
  background: transparent;
  border-radius: 6px;

  &:last-child { border-bottom: none; }
}

.evt-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-xs);
}

.evt-name {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 400;
  color: var(--accent-jade);
}

.evt-desc {
  font-family: var(--font-ui);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: 1.85;
  margin: 0;
}

.evt-impact {
  font-family: var(--font-ui);
  color: var(--text-primary);
  font-size: var(--fs-xs);
  line-height: 1.5;
  margin: var(--sp-xs) 0 0;
}
</style>
