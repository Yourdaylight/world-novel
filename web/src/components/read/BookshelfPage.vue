<template>
  <div class="bookshelf-page">
    <header class="page-head">
      <h1>我的书架</h1>
      <p class="page-sub">收藏的小说与阅读进度</p>
    </header>

    <div v-if="loading" class="state-hint">加载中…</div>
    <div v-else-if="items.length === 0" class="state-hint">
      书架还是空的 — 去阅读页把喜欢的书加入书架吧。
    </div>

    <div v-else class="shelf-list">
      <div v-for="item in items" :key="item.novel_id" class="shelf-card">
        <div class="shelf-info">
          <h3>{{ item.title }}</h3>
          <p class="shelf-meta">
            <span v-if="item.genre">{{ item.genre }}</span>
            <span>读到 第{{ item.chapter_index + 1 }}章</span>
            <span class="shelf-time">{{ formatTime(item.last_read_at) }}</span>
          </p>
        </div>
        <div class="shelf-actions">
          <button v-if="item.share_id" class="btn-read" @click="goRead(item)">
            继续阅读
          </button>
          <button class="btn-ghost" @click="remove(item)">移出书架</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getBookshelf, updateBookshelf, type BookshelfItem } from '@/api/share'

const router = useRouter()
const loading = ref(true)
const items = ref<BookshelfItem[]>([])

async function load() {
  loading.value = true
  try {
    const { data } = await getBookshelf()
    items.value = data.bookshelf || []
  } finally {
    loading.value = false
  }
}

function goRead(item: BookshelfItem) {
  router.push({
    name: 'read-chapter',
    params: { shareId: item.share_id, chapterIndex: String(item.chapter_index) },
  })
}

async function remove(item: BookshelfItem) {
  await updateBookshelf(item.novel_id, false)
  items.value = items.value.filter((i) => i.novel_id !== item.novel_id)
}

function formatTime(ts: string) {
  if (!ts) return ''
  return ts.replace('T', ' ').slice(0, 16)
}

onMounted(load)
</script>

<style scoped lang="scss">
.bookshelf-page {
  max-width: 760px;
  margin: 0 auto;
  padding: var(--sp-xl) var(--sp-md);
}

.page-head {
  margin-bottom: var(--sp-lg);

  h1 {
    margin: 0;
    font-size: var(--fs-lg);
  }

  .page-sub {
    color: var(--text-secondary);
    font-size: var(--fs-sm);
    margin: var(--sp-xs) 0 0;
  }
}

.state-hint {
  color: var(--text-muted);
  text-align: center;
  padding: var(--sp-2xl);
  font-size: var(--fs-sm);
}

.shelf-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}

.shelf-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  padding: var(--sp-md);

  h3 {
    margin: 0 0 var(--sp-xs);
    font-size: var(--fs-base);
  }
}

.shelf-meta {
  display: flex;
  gap: var(--sp-md);
  color: var(--text-muted);
  font-size: var(--fs-sm);
  margin: 0;
}

.shelf-actions {
  display: flex;
  gap: var(--sp-sm);
  flex-shrink: 0;
}

.btn-read {
  background: var(--accent-ember);
  border: none;
  color: #fff;
  padding: 7px 16px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--fs-sm);
}

.btn-ghost {
  border: 1px solid var(--border-default);
  background: none;
  color: var(--text-secondary);
  padding: 7px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--fs-sm);
}
</style>
