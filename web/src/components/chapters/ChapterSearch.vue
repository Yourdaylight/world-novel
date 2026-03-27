<template>
  <div class="chapter-search">
    <el-input
      v-model="chapterStore.searchQuery"
      placeholder="搜索章节..."
      prefix-icon="Search"
      clearable
      size="small"
      @input="onInput"
    />
  </div>
</template>

<script setup lang="ts">
import { useDebounceFn } from '@vueuse/core'
import { useChapterStore } from '@/stores/chapters'

const chapterStore = useChapterStore()

const onInput = useDebounceFn(() => {
  // The search is reactive via the store's computed filteredChapters
  // This debounce just prevents excessive recomputation
}, 300)
</script>

<style scoped lang="scss">
.chapter-search {
  margin-bottom: var(--sp-md);
}
</style>
