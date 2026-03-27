<template>
  <PanelCard title="势力阵营" icon="🏰">
    <template v-if="world.factions && world.factions.length">
      <div v-for="(faction, i) in world.factions" :key="i" class="faction-item">
        <div class="faction-name">{{ typeof faction === 'string' ? faction : faction.name || JSON.stringify(faction) }}</div>
        <p v-if="faction.description" class="faction-desc">{{ faction.description }}</p>
      </div>
    </template>
    <EmptyState v-else message="暂无势力数据" icon="🏰" />
  </PanelCard>
</template>

<script setup lang="ts">
import PanelCard from '@/components/common/PanelCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { WorldData } from '@/api/types'

defineProps<{ world: WorldData }>()
</script>

<style scoped lang="scss">
.faction-item {
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-rule);
  background: transparent;
  border-radius: 6px;

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
</style>
