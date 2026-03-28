<template>
  <div class="novel-page" v-loading="loading">
    <!-- Header -->
    <div class="novel-header ledger-rule" v-if="hasChapters">
      <div class="header-info">
        <h2 class="novel-title">{{ novelData.title }}</h2>
        <span class="novel-meta font-data">{{ novelData.chapters.length }}章 · {{ formatWordCount(novelData.word_count) }}</span>
      </div>
    </div>

    <!-- Main: TOC + Reader side by side -->
    <div class="novel-layout" v-if="hasChapters">
      <!-- Left: TOC -->
      <aside class="novel-toc">
        <span class="section-label">目录</span>
        <nav class="toc-list">
          <a v-for="ch in novelData.chapters" :key="ch.chapter_index"
             class="toc-item" :class="{ active: activeIndex === ch.chapter_index }"
             @click="goToChapter(ch.chapter_index)">
            <span class="toc-num">第{{ ch.chapter_index + 1 }}章</span>
            <span class="toc-title" v-if="ch.title">{{ ch.title }}</span>
            <span class="toc-words font-data">{{ ch.word_count.toLocaleString() }}字</span>
          </a>
        </nav>
        <div class="toc-footer">
          <el-dropdown trigger="click">
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
      </aside>

      <!-- Right: Reader -->
      <div class="novel-reader-area">
        <NovelReader v-if="activeChapter" :chapter="activeChapter" />
        <div class="chapter-nav">
          <el-button :disabled="activeIndex <= 0" @click="goToChapter(activeIndex - 1)">上一章</el-button>
          <span class="nav-pos font-data">{{ activeIndex + 1 }}/{{ novelData.chapters.length }}章</span>
          <el-button :disabled="activeIndex >= novelData.chapters.length - 1" @click="goToChapter(activeIndex + 1)">下一章</el-button>
        </div>
      </div>
    </div>

    <!-- Empty states -->
    <div class="empty-state" v-if="!loading && !hasChapters">
      <div v-if="isGenerating" class="empty-generating">
        <p class="empty-title">生成中...</p>
        <p class="empty-desc">章节完成后将自动出现在此处</p>
        <div class="empty-progress" v-if="progressStore.total > 0">
          <el-progress :percentage="progressStore.percent" :stroke-width="8" :show-text="true" :color="'#d4793a'" />
          <span class="font-data">{{ progressStore.completed }}/{{ progressStore.total }}章</span>
        </div>
      </div>
      <div v-else class="empty-idle">
        <p class="empty-title">暂无成书数据</p>
        <p class="empty-desc">请先在概览页面启动生成</p>
      </div>
    </div>

    <!-- File Manager (only shown with chapters) -->
    <div class="file-section ledger-rule" v-if="hasChapters">
      <span class="section-label">文件管理</span>
      <div class="file-manager" v-loading="filesLoading">
        <div v-if="files.length === 0" class="empty-files">暂无文件</div>
        <div v-for="f in files" :key="f.path" class="file-item">
          <span class="file-name">{{ f.name }}</span>
          <span class="file-size font-data">{{ formatFileSize(f.size) }}</span>
          <el-tag size="small" :type="f.source === 'historian' ? 'warning' : 'info'">{{ f.source === 'historian' ? '史官' : '角色' }}</el-tag>
          <el-button size="small" text type="primary" @click="downloadFile(f.path)">下载</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchNovelFull } from '@/api/chapters'
import { useProgressStore } from '@/stores/progress'
import { onWSEvent } from '@/composables/useWebSocket'
import NovelReader from './NovelReader.vue'
import client from '@/api/client'
import type { NovelFull } from '@/api/types'

const route = useRoute()
const progressStore = useProgressStore()
const loading = ref(false)
const filesLoading = ref(false)
const novelFull = ref<NovelFull | null>(null)
const files = ref<any[]>([])
const activeIndex = ref(0)

const hasChapters = computed(() => novelFull.value && novelFull.value.chapters.length > 0)
// Non-null assertion for template use inside v-if="hasChapters"
const novelData = computed(() => novelFull.value!)

const activeChapter = computed(() => {
  if (!novelFull.value || novelFull.value.chapters.length === 0) return null
  return novelFull.value.chapters[activeIndex.value] || novelFull.value.chapters[0]
})

const isGenerating = computed(() => {
  const p = progressStore.phase
  return p !== 'idle' && p !== 'done' && p !== 'error'
})

function goToChapter(index: number) {
  if (novelFull.value && index >= 0 && index < novelFull.value.chapters.length) {
    activeIndex.value = index
    window.scrollTo({ top: 0 })
  }
}

function formatWordCount(wc: number): string {
  if (wc > 10000) return `${(wc / 10000).toFixed(1)}万字`
  return `${wc.toLocaleString()}字`
}

async function loadNovel() {
  loading.value = true
  try {
    const data = await fetchNovelFull()
    if (data.chapters.length > 0) {
      novelFull.value = data
      if (activeIndex.value >= data.chapters.length) {
        activeIndex.value = data.chapters.length - 1
      }
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadNovel()
  loadFiles()
})

// Live updates
const unsubChapter = onWSEvent('chapter_completed', async () => {
  await loadNovel()
})
const unsubFinish = onWSEvent('generation_finished', async () => {
  await loadNovel()
})
onUnmounted(() => {
  unsubChapter()
  unsubFinish()
})

async function loadFiles() {
  const novelId = route.params.novelId as string
  if (!novelId) return
  filesLoading.value = true
  try {
    const { data } = await client.get(`/worlds/${novelId}/files`)
    files.value = data.files || []
  } catch { /* ignore */ }
  filesLoading.value = false
}

async function copyAll() {
  if (novelFull.value) {
    await navigator.clipboard.writeText(novelFull.value.full_text)
    ElMessage.success('全文已复制到剪贴板')
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

function downloadFile(path: string) {
  const novelId = route.params.novelId as string
  window.open(`/api/worlds/${novelId}/files/download?path=${encodeURIComponent(path)}`, '_blank')
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped lang="scss">
.novel-page {
  min-height: 400px;
}

/* ---- Header ---- */
.novel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--sp-lg);
  margin-bottom: var(--sp-lg);
}

.novel-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 var(--sp-xs) 0;
}

.novel-meta {
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

/* ---- Layout ---- */
.novel-layout {
  display: flex;
  gap: var(--sp-xl);
}

/* ---- TOC ---- */
.novel-toc {
  width: 200px;
  min-width: 200px;
  flex-shrink: 0;
  position: sticky;
  top: var(--sp-xl);
  max-height: calc(100vh - 120px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.section-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  display: block;
  margin-bottom: var(--sp-sm);
}

.toc-list {
  flex: 1;
  overflow-y: auto;
}

.toc-item {
  display: flex;
  flex-direction: column;
  padding: var(--sp-sm);
  cursor: pointer;
  border-left: 2px solid transparent;
  text-decoration: none;

  &:hover {
    background: var(--bg-elevated);
  }

  &.active {
    border-left-color: var(--accent-ember);
    background: var(--accent-ember-dim);
    .toc-num { color: var(--accent-ember); }
  }
}

.toc-num {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.toc-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

.toc-words {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

.toc-footer {
  padding-top: var(--sp-sm);
  border-top: 1px solid var(--border-default);
  margin-top: var(--sp-sm);
}

/* ---- Reader Area ---- */
.novel-reader-area {
  flex: 1;
  min-width: 0;
  max-width: 720px;
}

.chapter-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--sp-xl);
  margin-top: var(--sp-lg);
  border-top: 1px solid var(--border-default);
}

.nav-pos {
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

/* ---- Empty States ---- */
.empty-state {
  display: flex;
  justify-content: center;
  padding: 64px 0;
}

.empty-generating,
.empty-idle {
  text-align: center;
  max-width: 360px;
}

.empty-title {
  font-family: var(--font-display);
  font-size: var(--fs-lg);
  color: var(--text-primary);
  margin: 0 0 var(--sp-xs) 0;
}

.empty-desc {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
  margin: 0;
}

.empty-progress {
  margin-top: var(--sp-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-xs);

  .el-progress {
    width: 200px;
  }

  .font-data {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
}

/* ---- File Section ---- */
.file-section {
  margin-top: var(--sp-xl);
  padding-top: var(--sp-lg);
}

.file-manager {
  min-height: 40px;
  margin-top: var(--sp-md);
}

.empty-files {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  text-align: center;
  padding: var(--sp-lg);
}

.file-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-ghost);

  &:last-child { border-bottom: none; }

  .file-name {
    flex: 1;
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    color: var(--text-primary);
  }
  .file-size {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
}
</style>
