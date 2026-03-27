<template>
  <PanelCard title="地点场景" icon="🗺️">
    <template v-if="world.locations && world.locations.length">
      <div v-for="(loc, i) in world.locations" :key="i" class="location-item">
        <div class="loc-name">{{ typeof loc === 'string' ? loc : loc.name || JSON.stringify(loc) }}</div>
        <p v-if="loc.description" class="loc-desc">{{ loc.description }}</p>
      </div>
    </template>
    <EmptyState v-else message="暂无地点数据" icon="🗺️" />
  </PanelCard>
</template>

<script setup lang="ts">
import PanelCard from '@/components/common/PanelCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { WorldData } from '@/api/types'

defineProps<{ world: WorldData }>()
</script>

<style scoped lang="scss">
.location-item {
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-rule);
  background: transparent;
  border-radius: 6px;

  &:last-child { border-bottom: none; }
}

.loc-name {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 400;
  color: var(--accent-jade);
  margin-bottom: var(--sp-xs);
}

.loc-desc {
  font-family: var(--font-ui);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: 1.85;
}
</style>
