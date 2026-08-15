<template>
  <div class="chapters-page" v-loading="chapterStore.loading">
    <div class="page-container">
      <!-- Header with title + actions -->
      <header class="page-header">
        <div class="header-title">
          <h1 class="page-title">章节</h1>
          <p class="page-subtitle">浏览与导出生成的小说章节</p>
        </div>
        <div class="header-actions">
          <ChapterSearch />
          <el-dropdown trigger="click" v-if="chapterStore.chapters.length > 0">
            <button class="btn-gradient">
              导出
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="downloadMarkdown">Markdown</el-dropdown-item>
                <el-dropdown-item @click="downloadJSON">JSON</el-dropdown-item>
                <el-dropdown-item @click="copyAll">复制全文</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- Two-column content -->
      <div class="chapters-layout">
        <aside class="chapters-sidebar card">
          <span class="section-label">章节列表</span>
          <ChapterTabs />
        </aside>

        <section class="chapters-main">
          <div class="chapter-content card" v-if="chapterStore.activeChapter !== null">
            <div class="chapter-view-header">
              <h2 class="chapter-title">{{ chapterText?.title ? `第${chapterStore.activeChapter + 1}章 ${chapterText.title}` : `第${chapterStore.activeChapter + 1}章` }}</h2>
              <el-radio-group v-model="chapterStore.viewMode" size="small">
                <el-radio-button value="narrative">叙事视图</el-radio-button>
                <el-radio-button value="actions">行动日志</el-radio-button>
              </el-radio-group>
            </div>

            <NarrativeView
              v-if="chapterStore.viewMode === 'narrative'"
              :chapter-text="chapterText"
            />
            <ActionLogView
              v-else
              :actions="chapterStore.chapterActions"
            />
          </div>

          <LiveWritingPanel />
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChapterStore } from '@/stores/chapters'
import { onWSEvent } from '@/composables/useWebSocket'
import { fetchNovelFull } from '@/api/chapters'
import ChapterSearch from './ChapterSearch.vue'
import ChapterTabs from './ChapterTabs.vue'
import NarrativeView from './NarrativeView.vue'
import ActionLogView from './ActionLogView.vue'
import LiveWritingPanel from './LiveWritingPanel.vue'

const route = useRoute()
const chapterStore = useChapterStore()
const chapterText = computed(() => chapterStore.chapterText)

onMounted(async () => {
  await chapterStore.loadChapters()
  if (chapterStore.activeChapter !== null) {
    await chapterStore.selectChapter(chapterStore.activeChapter)
  }
})

// Auto-refresh chapter list on WS events
const unsubChapter = onWSEvent('chapter_completed', async () => {
  await chapterStore.loadChapters()
})
const unsubFinish = onWSEvent('generation_finished', async () => {
  await chapterStore.loadChapters()
})
onUnmounted(() => {
  unsubChapter()
  unsubFinish()
})

// Export functions (merged from NovelPage)
async function copyAll() {
  try {
    const data = await fetchNovelFull()
    if (data.full_text) {
      await navigator.clipboard.writeText(data.full_text)
      ElMessage.success('全文已复制到剪贴板')
    }
  } catch {
    ElMessage.error('复制失败')
  }
}

function downloadMarkdown() {
  const novelId = route.params.novelId as string
  window.open(`/api/worlds/${novelId}/export/markdown`, '_blank')
}

function downloadJSON() {
  const novelId = route.params.novelId as string
  window.open(`/api/worlds/${novelId}/export/json`, '_blank')
}
</script>

<style scoped lang="scss">
.chapters-page {
  min-height: calc(100vh - var(--header-height));
  background: var(--bg-void);
}

.page-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--sp-lg) var(--sp-lg);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
}

.header-title {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2xs);
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-2xl);
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.page-subtitle {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  flex-shrink: 0;
}

.btn-gradient {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #d97706, #b45309);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-base) ease;
  box-shadow: 0 2px 8px rgba(217, 119, 6, 0.22);

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(217, 119, 6, 0.35);
  }
}

.chapters-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: var(--sp-lg);
  align-items: start;
}

.chapters-sidebar {
  padding: var(--sp-md);
  position: sticky;
  top: calc(var(--header-height) + var(--sp-lg));
}

.chapters-main {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
  min-width: 0;
}

.chapter-content {
  padding: var(--sp-lg);
}

.chapter-view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
  padding-bottom: var(--sp-md);
  border-bottom: 1px solid var(--border-default);
}

.chapter-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: -0.01em;
  line-height: 1.3;
}

@media (max-width: 768px) {
  .page-container {
    padding: var(--sp-md) var(--sp-md);
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--sp-sm);
  }

  .header-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .chapters-layout {
    grid-template-columns: 1fr;
  }

  .chapters-sidebar {
    position: static;
  }

  .chapter-view-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
