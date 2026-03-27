<template>
  <div class="foreshadow-item">
    <div class="fs-header">
      <span :class="['fs-status', `status-${foreshadow.status}`]">{{ foreshadow.status }}</span>
      <el-tag size="small" :type="importanceType">{{ foreshadow.importance }}</el-tag>
      <span class="fs-chapters">
        第{{ foreshadow.planted_chapter + 1 }}章 → 第{{ foreshadow.expected_payoff_chapter + 1 }}章
        <template v-if="foreshadow.actual_payoff_chapter !== null">
          (实际: 第{{ foreshadow.actual_payoff_chapter + 1 }}章)
        </template>
      </span>
    </div>
    <p class="fs-desc">{{ foreshadow.description }}</p>
    <p class="fs-hint" v-if="foreshadow.hint_text">
      <span class="label">暗示：</span>{{ foreshadow.hint_text }}
    </p>
    <div class="fs-meta" v-if="foreshadow.related_characters.length">
      <el-tag v-for="c in foreshadow.related_characters" :key="c" size="small" type="info">{{ c }}</el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Foreshadow } from '@/api/types'

const props = defineProps<{ foreshadow: Foreshadow }>()

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const importanceType = computed((): TagType => {
  const map: Record<string, TagType> = { high: 'danger', medium: 'warning', low: 'info' }
  return map[props.foreshadow.importance] || 'info'
})
</script>

<style scoped lang="scss">
.foreshadow-item {
  padding: var(--sp-md) 0;
  border-bottom: 1px solid var(--border-rule);
  background: transparent;
  border-radius: 6px;

  &:last-child { border-bottom: none; }
}

.fs-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-sm);
  flex-wrap: wrap;
}

.fs-status {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;

  &.status-planted { color: var(--accent-aurora); }
  &.status-activated { color: var(--accent-aurora); }
  &.status-resolved { color: var(--accent-jade); }
  &.status-abandoned { color: var(--accent-cinnabar); }
}

.fs-chapters {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.fs-desc {
  font-family: var(--font-ui);
  font-style: italic;
  color: var(--text-secondary);
  line-height: 1.85;
  margin-bottom: var(--sp-sm);
}

.fs-hint {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
  margin-bottom: var(--sp-sm);
  font-style: italic;

  .label {
    font-family: var(--font-ui);
    font-weight: 600;
    font-style: normal;
    color: var(--text-secondary);
  }
}

.fs-meta {
  display: flex;
  gap: var(--sp-sm);
  flex-wrap: wrap;
}
</style>
