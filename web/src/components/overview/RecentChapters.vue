<template>
  <section class="recent-chapters-card">
    <div class="card-header">
      <div>
        <div class="eyebrow">Recent Chapters</div>
        <h3 class="title">最近章节</h3>
      </div>
      <el-tag size="small" type="info">{{ chapters.length }} 章</el-tag>
    </div>

    <div v-if="loading" class="state-block" v-loading="true" />
    <div v-else-if="chapters.length === 0" class="state-block empty">
      暂无已生成章节
    </div>
    <div v-else class="chapter-grid">
      <button
        v-for="chapter in recentChapters"
        :key="chapter.chapter_index"
        class="chapter-item"
        type="button"
        @click="goToChapter(chapter.chapter_index)"
      >
        <div class="chapter-topline">
          <span class="chapter-badge">第{{ chapter.chapter_index + 1 }}章</span>
          <el-tag :type="chapter.has_text ? 'success' : 'warning'" size="small">
            {{ chapter.has_text ? '已成文' : '仅轨迹' }}
          </el-tag>
        </div>
        <div class="chapter-title">
          {{ chapter.has_text ? '查看章节内容' : '查看场景行动记录' }}
        </div>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { fetchChapters } from '@/api/chapters'
import type { ChapterInfo } from '@/api/types'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const chapters = ref<ChapterInfo[]>([])

const recentChapters = computed(() => [...chapters.value].sort((a, b) => b.chapter_index - a.chapter_index).slice(0, 6))

async function loadRecentChapters() {
  loading.value = true
  try {
    const data = await fetchChapters()
    chapters.value = data.chapters || []
  } catch {
    chapters.value = []
  } finally {
    loading.value = false
  }
}

function goToChapter(chapterIndex: number) {
  const novelId = route.params.novelId as string | undefined
  if (novelId) {
    router.push({ path: `/novels/${novelId}/chapters`, query: { chapter: String(chapterIndex) } })
    return
  }
  router.push({ path: '/chapters', query: { chapter: String(chapterIndex) } })
}

onMounted(() => {
  loadRecentChapters()
})
</script>

<style scoped lang="scss">
.recent-chapters-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--sp-lg);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  margin-bottom: var(--sp-md);
}

.eyebrow {
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.title {
  margin: 4px 0 0;
  font-size: var(--fs-lg);
  color: var(--text-primary);
}

.state-block {
  min-height: 120px;
  border-radius: var(--radius-md);
}

.state-block.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.02);
  border: 1px dashed var(--border-default);
}

.chapter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--sp-md);
}

.chapter-item {
  appearance: none;
  text-align: left;
  width: 100%;
  border: 1px solid var(--border-default);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.01));
  border-radius: var(--radius-md);
  padding: var(--sp-md);
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;

  &:hover {
    transform: translateY(-2px);
    border-color: var(--accent-aurora);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }
}

.chapter-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-sm);
}

.chapter-badge {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--accent-ember);
  font-weight: 600;
}

.chapter-title {
  color: var(--text-primary);
  line-height: 1.5;
}
</style>
