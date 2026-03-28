<template>
  <div class="chapters-page" v-loading="chapterStore.loading">
    <!-- Header with search + export -->
    <div class="chapters-header">
      <ChapterSearch />
      <el-dropdown trigger="click" v-if="chapterStore.chapters.length > 0">
        <el-button size="small">导出</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="downloadMarkdown">Markdown</el-dropdown-item>
            <el-dropdown-item @click="downloadJSON">JSON</el-dropdown-item>
            <el-dropdown-item @click="copyAll">复制全文</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-row :gutter="20">
      <el-col :span="6">
        <div class="ledger-zone">
          <span class="section-label">章节列表</span>
          <ChapterTabs />
        </div>
      </el-col>
      <el-col :span="18">
        <div class="ledger-zone" v-if="chapterStore.activeChapter !== null">
          <div class="chapter-view-header ledger-rule">
            <span class="chapter-title">{{ chapterText?.title ? `第${chapterStore.activeChapter + 1}章 ${chapterText.title}` : `第${chapterStore.activeChapter + 1}章` }}</span>
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

        <!-- Live writing panel -->
        <LiveWritingPanel />
      </el-col>
    </el-row>
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
.chapters-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  margin-bottom: var(--sp-md);
}

.ledger-zone {
  padding-bottom: var(--sp-lg);
}

.chapter-view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.chapter-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
}
</style>
