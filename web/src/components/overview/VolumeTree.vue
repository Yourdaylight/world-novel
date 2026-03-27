<template>
  <PanelCard title="卷册结构" icon="📚">
    <template v-if="worldStore.volumes.length">
      <div class="volume-list">
        <div v-for="vol in worldStore.volumes" :key="vol.volume_index" class="volume-item ledger-rule">
          <div class="volume-header">
            <span class="volume-index">第{{ vol.volume_index + 1 }}卷</span>
            <span class="volume-title">{{ vol.title }}</span>
            <span class="volume-range">{{ vol.chapter_start + 1 }}–{{ vol.chapter_end + 1 }}章</span>
          </div>
          <p class="volume-summary" v-if="vol.summary">{{ vol.summary }}</p>
          <div class="volume-meta">
            <span v-if="vol.theme" class="meta-tag">🎭 {{ vol.theme }}</span>
            <span v-if="vol.arc_goal" class="meta-tag">🎯 {{ vol.arc_goal }}</span>
          </div>
        </div>
      </div>
    </template>
    <EmptyState v-else message="暂无卷册数据" />
  </PanelCard>
</template>

<script setup lang="ts">
import PanelCard from '@/components/common/PanelCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useWorldStore } from '@/stores/world'

const worldStore = useWorldStore()
</script>

<style scoped lang="scss">
.volume-list {
  display: flex;
  flex-direction: column;
}
.volume-item {
  padding: var(--sp-md) 0;
  border-left: 3px solid var(--accent-aurora);
  padding-left: var(--sp-md);
  border-radius: 6px;
  background: transparent;
}
.volume-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-sm);
}
.volume-index {
  font-family: var(--font-data);
  font-weight: 600;
  font-size: var(--fs-sm);
  color: var(--accent-aurora);
}
.volume-title {
  font-family: var(--font-ui);
  font-weight: 600;
  font-size: var(--fs-base);
  color: var(--text-primary);
}
.volume-range {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  margin-left: auto;
}
.volume-summary {
  font-family: var(--font-ui);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: 1.85;
  margin-bottom: var(--sp-sm);
}
.volume-meta {
  display: flex;
  gap: var(--sp-md);
}
.meta-tag {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}
</style>
