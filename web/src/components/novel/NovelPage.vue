<template>
  <div class="novel-page" v-loading="loading">
    <PanelCard v-if="novelFull">
      <template #header>
        <div class="novel-header">
          <div>
            <h2>{{ novelFull.title }}</h2>
            <span class="novel-meta">{{ novelFull.genre }} · {{ novelFull.word_count.toLocaleString() }} 字 · {{ novelFull.chapters.length }} 章</span>
          </div>
          <div class="header-actions">
            <el-button type="primary" @click="downloadMarkdown">📥 导出 Markdown</el-button>
            <el-button @click="downloadJSON">📦 导出世界数据</el-button>
            <el-button @click="copyAll">📋 复制全文</el-button>
          </div>
        </div>
      </template>
      <NovelReader :chapters="novelFull.chapters" />
    </PanelCard>

    <!-- File Manager -->
    <PanelCard title="文件管理" icon="📁" style="margin-top: 1rem">
      <div class="file-manager" v-loading="filesLoading">
        <div v-if="files.length === 0" class="empty-files">暂无文件（史官输出的文档会出现在此处）</div>
        <div v-for="f in files" :key="f.path" class="file-item">
          <span class="file-icon">{{ f.source === 'historian' ? '📜' : '🤖' }}</span>
          <span class="file-name">{{ f.name }}</span>
          <span class="file-size">{{ formatFileSize(f.size) }}</span>
          <el-tag size="small" :type="f.source === 'historian' ? 'warning' : 'info'">
            {{ f.source === 'historian' ? '史官' : '角色' }}
          </el-tag>
          <el-button size="small" text type="primary" @click="downloadFile(f.path)">下载</el-button>
        </div>
      </div>
    </PanelCard>

    <EmptyState v-if="!loading && !novelFull" message="暂无成书数据，请先完成章节创作" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchNovelFull } from '@/api/chapters'
import PanelCard from '@/components/common/PanelCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import NovelReader from './NovelReader.vue'
import client from '@/api/client'
import type { NovelFull } from '@/api/types'

const route = useRoute()
const loading = ref(false)
const filesLoading = ref(false)
const novelFull = ref<NovelFull | null>(null)
const files = ref<any[]>([])

onMounted(async () => {
  loading.value = true
  try {
    const data = await fetchNovelFull()
    if (data.chapters.length > 0) novelFull.value = data
  } finally {
    loading.value = false
  }
  loadFiles()
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
  const url = `/api/worlds/${novelId}/export/json`
  window.open(url, '_blank')
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
.novel-header {
  display: flex; align-items: center; justify-content: space-between; width: 100%;
  h2 { margin-bottom: 0.25rem; }
  .header-actions { display: flex; gap: 0.5rem; }
}
.novel-meta { font-size: 0.85rem; color: var(--text-muted); }

.file-manager {
  min-height: 60px;
}
.empty-files { color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 1.5rem; }
.file-item {
  display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  .file-icon { font-size: 1.1rem; }
  .file-name { flex: 1; font-size: 0.88rem; color: var(--text-primary); }
  .file-size { font-size: 0.75rem; color: var(--text-muted); }
}
</style>
