<template>
  <div class="card world-card">
    <div class="card-header">
      <span class="card-icon">📜</span>
      <span class="card-title">历史事件</span>
    </div>
    <div class="card-body">
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
      <EmptyState v-else message="暂无历史事件" icon="📜" class="compact-empty" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
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
.world-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-md);
  border-bottom: 1px solid var(--border-muted);
}

.card-icon {
  font-size: 1.1rem;
  opacity: 0.7;
}

.card-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.card-body {
  padding: var(--sp-md);
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.event-item {
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-rule);

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

:deep(.empty-state.compact-empty) {
  padding: var(--sp-lg) var(--sp-md);
}
</style>
