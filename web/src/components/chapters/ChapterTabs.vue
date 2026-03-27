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
  max-height: 500px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.chapter-tab-item {
  padding: 6px 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-ghost);
  font-family: var(--font-ui);
  color: var(--text-secondary);
  transition: none;

  &:hover {
    color: var(--text-primary);
  }

  &.active {
    color: var(--accent-ember);
    border-bottom-color: var(--accent-ember);

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
