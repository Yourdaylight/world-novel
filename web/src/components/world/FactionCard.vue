<template>
  <div class="card world-card">
    <div class="card-header">
      <span class="card-icon">🏰</span>
      <span class="card-title">势力阵营</span>
    </div>
    <div class="card-body">
      <template v-if="world.factions && world.factions.length">
        <div v-for="(faction, i) in world.factions" :key="i" class="faction-item">
          <div class="faction-name">{{ typeof faction === 'string' ? faction : faction.name || JSON.stringify(faction) }}</div>
          <p v-if="faction.description" class="faction-desc">{{ faction.description }}</p>
        </div>
      </template>
      <EmptyState v-else message="暂无势力数据" icon="🏰" class="compact-empty" />
    </div>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/common/EmptyState.vue'
import type { WorldData } from '@/api/types'

defineProps<{ world: WorldData }>()
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

.faction-item {
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-rule);

  &:last-child { border-bottom: none; }
}

.faction-name {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 400;
  color: var(--accent-aurora);
  margin-bottom: var(--sp-xs);
}

.faction-desc {
  font-family: var(--font-ui);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: 1.85;
}

:deep(.empty-state.compact-empty) {
  padding: var(--sp-lg) var(--sp-md);
}
</style>
