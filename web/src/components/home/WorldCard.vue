<template>
  <div class="world-card animate-fade-up" @click="$emit('enter', novel)">
    <!-- Top bar: genre + status -->
    <div class="card-header">
      <span class="genre-badge">{{ novel.genre || '未分类' }}</span>
      <span :class="['status-pill', `status-${novel.status}`]">
        <span class="pill-dot" v-if="novel.status === 'generating'"></span>
        {{ statusLabel }}
      </span>
    </div>

    <!-- Title -->
    <h3 class="card-title">{{ novel.title }}</h3>

    <!-- Meta info -->
    <div class="card-meta">
      <div class="meta-row">
        <span class="meta-label">进度</span>
        <div class="meta-progress-track">
          <div
            class="meta-progress-fill"
            :style="{ width: `${progressPercent}%`, background: progressGradient }"
          ></div>
        </div>
        <span class="meta-value font-data">{{ novel.chapters_completed }}/{{ novel.chapters_total || '?' }} 章</span>
      </div>
      <div class="meta-row" v-if="novel.word_count">
        <span class="meta-label">字数</span>
        <span class="meta-value font-data">{{ formatWordCount(novel.word_count) }}</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="card-actions">
      <button class="action-btn action-primary" @click.stop="$emit('enter', novel)">
        进入仪表板
      </button>
      <button
        v-if="novel.status !== 'completed' && novel.status !== 'generating'"
        class="action-btn action-run"
        @click.stop="$emit('run', novel)"
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
        运行
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
  simulating: '模拟中',
  prepared: '准备就绪',
  simulated: '模拟完成',
}

const statusLabel = computed(() => statusLabels[props.novel.status] || props.novel.status)

const progressPercent = computed(() => {
  if (!props.novel.chapters_total) return 0
  return Math.round((props.novel.chapters_completed / props.novel.chapters_total) * 100)
})

const progressColor = computed(() => {
  switch (props.novel.status) {
    case 'completed': return '#059669'
    case 'generating': return '#d97706'
    case 'paused': return '#6b7280'
    default: return varToValue('--text-muted')
  }
})

const progressGradient = computed(() => {
  const c = progressColor.value
  return `linear-gradient(90deg, ${c}, ${c}aa)`
})

function varToValue(v: string): string {
  return '#90909a' // fallback for non-CSS-context usage
}

function formatWordCount(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toLocaleString()
}
</script>

<style scoped lang="scss">
.world-card {
  position: relative;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--sp-md);
  cursor: pointer;
  transition: all var(--duration-base) ease;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent-ember), transparent);
    opacity: 0;
    transition: opacity var(--duration-base) ease;
  }

  &:hover {
    border-color: var(--border-active);
    box-shadow: var(--shadow-deep), 0 0 0 1px rgba(217,119,6,0.05);
    transform: translateY(-3px);

    &::before { opacity: 1; }
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
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
}

.status-pill {
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
  display: inline-flex;
  align-items: center;
  gap: 4px;

  .pill-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
    animation: dot-pulse 2s ease-in-out infinite;
  }

  &.status-idle     { color: var(--text-muted); background: var(--bg-elevated); }
  &.status-generating { color: #d97706; background: rgba(217,119,6,0.10); }
  &.status-paused   { color: #60a5fa; background: rgba(96,165,250,0.10); }
  &.status-completed { color: var(--accent-jade); background: rgba(5,150,105,0.10); }
}

.card-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 var(--sp-md) 0;
  line-height: 1.25;
  letter-spacing: -0.01em;
}

.card-meta {
  margin-bottom: var(--sp-md);
  padding-top: var(--sp-sm);
  border-top: 1px solid var(--border-muted);
}

.meta-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: 6px;

  &:last-child { margin-bottom: 0; }
}

.meta-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  min-width: 28px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 500;
}

.meta-value {
  font-family: var(--font-data);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.meta-progress-track {
  flex: 1;
  max-width: 100px;
  height: 4px;
  background: var(--bg-elevated);
  border-radius: 2px;
  overflow: hidden;
}

.meta-progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s var(--ease-out-expo);
}

.card-actions {
  display: flex;
  gap: var(--sp-xs);
  padding-top: var(--p-sm, var(--sp-sm));
  border-top: 1px solid var(--border-muted);
}

.action-btn {
  border: none;
  border-radius: var(--radius-sm);
  padding: 7px 14px;
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-base) ease;
  letter-spacing: 0.01em;

  &.action-primary {
    background: linear-gradient(135deg, #d97706, #b45309);
    color: #fff;
    flex: 1;

    &:hover {
      opacity: 0.92;
      transform: translateY(-1px);
      box-shadow: 0 3px 10px rgba(217,119,6,0.3);
    }
  }

  &.action-run {
    background: transparent;
    border: 1px solid var(--accent-jade);
    color: var(--accent-jade);
    display: inline-flex;
    align-items: center;
    gap: 4px;

    &:hover { background: rgba(5,150,105,0.06); }
  }

  &.action-delete {
    background: transparent;
    border: 1px solid var(--border-default);
    color: var(--text-muted);
    margin-left: auto;

    &:hover {
      color: var(--accent-cinnabar);
      border-color: rgba(220,38,38,0.35);
      background: rgba(220,38,38,0.04);
    }
  }
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.4; transform: scale(0.85); }
}
</style>