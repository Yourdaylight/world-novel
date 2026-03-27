<template>
  <div class="novel-reader">
    <div v-for="ch in chapters" :key="ch.chapter_index" class="reader-chapter">
      <h3 class="chapter-title">第{{ ch.chapter_index + 1 }}章 {{ ch.title }}</h3>
      <div class="chapter-text" v-html="renderText(ch.text)"></div>
      <div class="chapter-word-count">{{ ch.word_count }} 字</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { escapeHtml } from '@/utils/escapeHtml'
import type { NovelFullChapter } from '@/api/types'

defineProps<{ chapters: NovelFullChapter[] }>()

function renderText(text: string): string {
  return escapeHtml(text)
    .split('\n')
    .filter((l) => l.trim())
    .map((l) => `<p style="text-indent:2em;line-height:2;margin-bottom:0.5em">${l}</p>`)
    .join('')
}
</script>

<style scoped lang="scss">
.novel-reader {
  max-height: 70vh;
  overflow-y: auto;
}
.reader-chapter {
  margin-bottom: 3rem;
}
.chapter-title {
  font-size: 1.3rem;
  color: var(--accent-blue);
  margin-bottom: 1.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}
.chapter-text {
  color: var(--text-primary);
  font-size: 1rem;
}
.chapter-word-count {
  text-align: right;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
}
</style>
