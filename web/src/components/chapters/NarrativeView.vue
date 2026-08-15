<template>
  <div class="narrative-view">
    <template v-if="chapterText && chapterText.scenes.length">
      <div class="summary card" v-if="chapterText.summary">
        <span class="section-label">摘要</span>
        <p>{{ chapterText.summary }}</p>
      </div>
      <div v-for="scene in chapterText.scenes" :key="scene.scene_index" class="scene-block card">
        <div class="scene-header">
          <span class="scene-label">场景 {{ scene.scene_index + 1 }}</span>
          <el-tag v-if="scene.pov_character" size="small" type="info">视角: {{ scene.pov_character }}</el-tag>
        </div>
        <div class="scene-content" v-html="renderText(scene.content)"></div>
      </div>
    </template>
    <EmptyState v-else message="暂无叙事文本" icon="📖" />
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/common/EmptyState.vue'
import { escapeHtml } from '@/utils/escapeHtml'
import type { ChapterText } from '@/api/types'

defineProps<{ chapterText: ChapterText | null }>()

function renderText(text: string): string {
  return escapeHtml(text).replace(/\n/g, '<br>')
}
</script>

<style scoped lang="scss">
.narrative-view {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
}

.summary {
  padding: var(--sp-md);

  p {
    font-family: var(--font-ui);
    color: var(--text-secondary);
    line-height: 1.7;
    font-size: var(--fs-sm);
  }
}

.scene-block {
  padding: var(--sp-lg);
}

.scene-header {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  margin-bottom: var(--sp-md);
  padding-bottom: var(--sp-sm);
  border-bottom: 1px solid var(--border-default);
}

.scene-label {
  font-family: var(--font-ui);
  font-weight: 600;
  font-size: var(--fs-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.scene-content {
  font-family: var(--font-ui);
  line-height: 2.0;
  font-size: var(--fs-md);
  color: var(--text-primary);
  text-indent: 2em;
}
</style>
