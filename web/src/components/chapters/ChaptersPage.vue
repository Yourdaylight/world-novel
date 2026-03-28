<template>
  <div class="chapters-page" v-loading="chapterStore.loading">
    <!-- Search bar -->
    <ChapterSearch />

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
import { onMounted, computed } from 'vue'
import { useChapterStore } from '@/stores/chapters'
import ChapterSearch from './ChapterSearch.vue'
import ChapterTabs from './ChapterTabs.vue'
import NarrativeView from './NarrativeView.vue'
import ActionLogView from './ActionLogView.vue'
import LiveWritingPanel from './LiveWritingPanel.vue'

const chapterStore = useChapterStore()
const chapterText = computed(() => chapterStore.chapterText)

onMounted(async () => {
  await chapterStore.loadChapters()
  if (chapterStore.activeChapter !== null) {
    await chapterStore.selectChapter(chapterStore.activeChapter)
  }
})
</script>

<style scoped lang="scss">
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
