<template>
  <div class="action-log-view">
    <template v-if="actions.length">
      <div v-for="(action, i) in actions" :key="i" class="action-item">
        <div class="action-header">
          <el-tag size="small" :type="actionTypeColor(action.action_type)">{{ action.action_type }}</el-tag>
          <span class="action-char">{{ action.character_id }}</span>
          <span class="action-scene">场景 {{ action.scene_index + 1 }}</span>
          <span v-if="action.target" class="action-target">→ {{ action.target }}</span>
        </div>
        <p class="action-content">{{ action.content }}</p>
      </div>
    </template>
    <EmptyState v-else message="暂无行动日志" icon="🎬" />
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/common/EmptyState.vue'
import type { ChapterAction } from '@/api/types'

defineProps<{ actions: ChapterAction[] }>()

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function actionTypeColor(type: string): TagType {
  const map: Record<string, TagType> = {
    dialogue: 'primary',
    action: 'success',
    thought: 'warning',
    narration: 'info',
  }
  return map[type] || 'info'
}
</script>

<style scoped lang="scss">
.action-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--border-ghost);
}

.action-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-xs);
  flex-wrap: wrap;
}

.action-char {
  font-family: var(--font-ui);
  font-weight: 600;
  font-size: var(--fs-sm);
  color: var(--text-primary);
}

.action-scene {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.action-target {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--accent-ember);
}

.action-content {
  font-family: var(--font-ui);
  color: var(--text-secondary);
  line-height: 1.85;
  font-size: var(--fs-sm);
}
</style>
