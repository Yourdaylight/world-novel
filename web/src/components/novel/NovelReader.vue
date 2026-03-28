<template>
  <div class="novel-reader">
    <h3 class="chapter-heading">第{{ chapter.chapter_index + 1 }}章 {{ chapter.title }}</h3>
    <div class="chapter-body">
      <p
        v-for="(para, i) in paragraphs"
        :key="i"
        class="chapter-paragraph"
      >{{ para }}</p>
    </div>
    <div class="chapter-footer ledger-rule">
      <span class="word-count font-data">{{ chapter.word_count.toLocaleString() }} 字</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NovelFullChapter } from '@/api/types'

const props = defineProps<{ chapter: NovelFullChapter }>()

const paragraphs = computed(() =>
  props.chapter.text
    .split('\n')
    .map(l => l.trim())
    .filter(Boolean)
)
</script>

<style scoped lang="scss">
.novel-reader {
  /* No max-height — content flows naturally */
}

.chapter-heading {
  font-family: var(--font-display);
  font-size: var(--fs-lg);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 var(--sp-xl) 0;
  padding-bottom: var(--sp-md);
  border-bottom: 1px solid var(--border-rule);
}

.chapter-body {
  font-family: var(--font-serif, 'Source Serif 4', serif);
  font-size: var(--fs-md);
  color: var(--text-primary);
  line-height: 1.8;
}

.chapter-paragraph {
  text-indent: 2em;
  margin: 0 0 1em 0;
}

.chapter-footer {
  text-align: right;
  padding-top: var(--sp-md);
  margin-top: var(--sp-lg);
}

.word-count {
  font-size: var(--fs-xs);
  color: var(--text-muted);
}
</style>
