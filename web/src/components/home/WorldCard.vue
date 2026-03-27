<template>
  <div class="world-card" @click="$emit('enter', novel)">
    <div class="card-header">
      <span class="genre-badge">{{ novel.genre || '未分类' }}</span>
      <span :class="['status-dot', `status-${novel.status}`]">{{ statusLabel }}</span>
    </div>
    <h3 class="card-title">{{ novel.title }}</h3>
    <div class="card-meta">
      <div class="meta-item">
        <span class="meta-label">进度</span>
        <el-progress
          :percentage="progressPercent"
          :stroke-width="4"
          :show-text="false"
          :color="progressColor"
        />
        <span class="meta-value">{{ novel.chapters_completed }}/{{ novel.chapters_total || '?' }} 章</span>
      </div>
      <div class="meta-item" v-if="novel.word_count">
        <span class="meta-label">字数</span>
        <span class="meta-value">{{ (novel.word_count || 0).toLocaleString() }}</span>
      </div>
    </div>
    <div class="card-actions">
      <button class="action-btn action-enter" @click.stop="$emit('enter', novel)">
        进入仪表板
      </button>
      <button
        v-if="novel.status !== 'completed' && novel.status !== 'generating'"
        class="action-btn action-run"
        @click.stop="$emit('run', novel)"
      >
        ▶ 运行
      </button>
      <button class="action-btn action-delete" @click.stop="$emit('delete', novel)">
        删除
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NovelInfo } from '@/api/types'

const props = defineProps<{
  novel: NovelInfo
}>()

defineEmits<{
  enter: [novel: NovelInfo]
  run: [novel: NovelInfo]
  delete: [novel: NovelInfo]
}>()

const statusLabels: Record<string, string> = {
  idle: '待运行',
  generating: '生成中',
  paused: '已暂停',
  completed: '已完成',
}

const statusLabel = computed(() => statusLabels[props.novel.status] || props.novel.status)

const progressPercent = computed(() => {
  if (!props.novel.chapters_total) return 0
  return Math.round((props.novel.chapters_completed / props.novel.chapters_total) * 100)
})

const progressColor = computed(() => {
  switch (props.novel.status) {
    case 'completed': return '#4ec994'
    case 'generating': return '#c6e847'
    case 'paused': return '#d4793a'
    default: return '#58505f'
  }
})
</script>

<style scoped lang="scss">
.world-card {
  margin-bottom: var(--sp-md);
  background: transparent;
  border: 1px solid var(--border-rule);
  padding: var(--sp-md);
  cursor: pointer;
  border-radius: 6px;

  &:hover {
    border-color: var(--border-active);
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-sm);
}

.genre-badge {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.status-dot {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: 2px;

  &.status-idle { color: var(--text-muted); }
  &.status-generating { color: var(--accent-phosphor); animation: ember-pulse 3s ease-in-out infinite; }
  &.status-paused { color: var(--text-muted); }
  &.status-completed { color: var(--accent-jade); }
}

.card-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 var(--sp-md) 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}

.card-meta {
  margin-bottom: var(--sp-md);
  border-top: 1px solid var(--border-ghost);
  padding-top: var(--sp-sm);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-xs);

  .meta-label {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    color: var(--text-muted);
    min-width: 2.5rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .meta-value {
    font-family: var(--font-data);
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .el-progress {
    flex: 1;
  }
}

.card-actions {
  display: flex;
  gap: var(--sp-sm);
  border-top: 1px solid var(--border-ghost);
  padding-top: var(--sp-sm);
}

.action-btn {
  border: none;
  border-radius: 6px;
  padding: var(--sp-xs) var(--sp-md);
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  cursor: pointer;

  &.action-enter {
    background: var(--accent-ember);
    color: var(--text-inverse);
    &:hover { background: #db8a52; }
  }

  &.action-run {
    background: transparent;
    border: 1px solid var(--accent-jade);
    color: var(--accent-jade);
    &:hover { background: rgba(78, 201, 148, 0.1); }
  }

  &.action-delete {
    background: transparent;
    border: 1px solid var(--border-rule);
    color: var(--text-muted);
    margin-left: auto;
    &:hover { color: var(--accent-cinnabar); border-color: var(--accent-cinnabar); }
  }
}

@keyframes ember-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
