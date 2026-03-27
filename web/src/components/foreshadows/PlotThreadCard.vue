<template>
  <div class="plot-thread-card">
    <div class="pt-header">
      <span class="pt-name">{{ thread.name }}</span>
      <span :class="['pt-status', thread.status === 'active' ? 'active' : 'inactive']">{{ thread.status }}</span>
    </div>
    <p class="pt-desc">{{ thread.description }}</p>
    <div class="pt-meta">
      <span class="meta-item" v-if="thread.start_chapter !== undefined">起始: 第{{ thread.start_chapter + 1 }}章</span>
      <span class="meta-item" v-if="thread.key_characters.length">
        角色: {{ thread.key_characters.join('、') }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PlotThread } from '@/api/types'

defineProps<{ thread: PlotThread }>()
</script>

<style scoped lang="scss">
.plot-thread-card {
  padding: var(--sp-md) 0;
  border-bottom: 1px solid var(--border-rule);
  background: transparent;
  border-radius: 6px;

  &:last-child { border-bottom: none; }
}

.pt-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-sm);
}

.pt-name {
  font-family: var(--font-ui);
  font-weight: 500;
  color: var(--text-primary);
}

.pt-status {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;

  &.active { color: var(--accent-jade); }
  &.inactive { color: var(--text-muted); }
}

.pt-desc {
  font-family: var(--font-ui);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: 1.85;
  margin-bottom: var(--sp-sm);
}

.pt-meta {
  display: flex;
  gap: var(--sp-md);
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}
</style>
