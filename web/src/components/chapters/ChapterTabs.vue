<template>
  <div class="chapter-tabs">
    <div
      v-for="ch in chapterStore.filteredChapters"
      :key="ch.chapter_index"
      class="chapter-tab-item"
      :class="{ active: ch.chapter_index === chapterStore.activeChapter }"
      @click="chapterStore.selectChapter(ch.chapter_index)"
    >
      <span class="ch-label">第{{ ch.chapter_index + 1 }}章</span>
      <el-tag v-if="ch.has_text" size="small" type="success">已渲染</el-tag>
      <el-tag v-else size="small" type="info">仅行动</el-tag>
    </div>
    <EmptyState v-if="!chapterStore.filteredChapters.length" message="没有匹配的章节" icon="🔍" />
  </div>
</template>

<script setup lang="ts">
import { useChapterStore } from '@/stores/chapters'
import EmptyState from '@/components/common/EmptyState.vue'

const chapterStore = useChapterStore()
</script>

<style scoped lang="scss">
.chapter-tabs {
  max-height: calc(100vh - var(--header-height) - var(--sp-lg) * 4);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2xs);
}

.chapter-tab-item {
  padding: var(--sp-sm) var(--sp-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-sm);
  border-radius: var(--radius-md);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  transition: all var(--duration-fast) ease;

  &:hover {
    color: var(--text-primary);
    background: var(--bg-elevated);
  }

  &.active {
    color: var(--accent-ember);
    background: var(--accent-ember-dim);
    font-weight: 600;

    .ch-label {
      font-weight: 600;
    }
  }
}

.ch-label {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 500;
}
</style>
