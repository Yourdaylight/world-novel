<template>
  <div class="reader-page">
    <!-- 顶栏 -->
    <header class="reader-header">
      <div class="header-inner">
        <router-link to="/" class="brand">
          <span class="brand-mark">✦</span> WorldNovel
        </router-link>
        <div class="header-actions">
          <button v-if="catalogOpen" class="btn-text" @click="catalogOpen = false">收起目录</button>
          <button v-else class="btn-text" @click="catalogOpen = true">目录</button>
          <template v-if="meta">
            <span v-if="meta.access.authenticated" class="user-badge">
              {{ meta.access.level === 'author' ? '作者' : '已登录' }}
            </span>
            <button v-else class="btn-cta" @click="goLogin">注册 / 登录读全书</button>
          </template>
        </div>
      </div>
    </header>

    <!-- 加载 / 错误 -->
    <div v-if="loading" class="state-row">正在打开分享…</div>
    <div v-else-if="notFound" class="state-box">
      <h2>分享不存在或已关闭</h2>
      <p>作者可能已取消该分享链接。</p>
      <router-link to="/" class="btn-cta-inline">返回首页</router-link>
    </div>

    <template v-else-if="meta">
      <!-- 目录抽屉 -->
      <transition name="slide">
        <aside v-if="catalogOpen" class="catalog-panel">
          <div class="catalog-head">
            <strong>目录</strong>
            <span class="catalog-meta">共 {{ catalog?.total ?? 0 }} 章 · 试读 {{ catalog?.trial_chapter_count ?? 0 }} 章</span>
          </div>
          <ul class="catalog-list">
            <li
              v-for="ch in catalog?.chapters"
              :key="ch.chapter_index"
              class="catalog-item"
              :class="{ active: ch.chapter_index === currentIndex, locked: !ch.readable }"
              @click="selectChapter(ch.chapter_index, ch.readable)"
            >
              <span class="chapter-title">第{{ ch.chapter_index + 1 }}章 {{ ch.title }}</span>
              <span v-if="!ch.readable" class="lock-icon">🔒</span>
            </li>
          </ul>
        </aside>
      </transition>

      <!-- 正文区 -->
      <main class="reader-main" @click="catalogOpen = false">
        <article v-if="chapter" class="chapter-card">
          <h1 class="chapter-heading">第{{ chapter.chapter_index + 1 }}章 {{ chapter.title }}</h1>
          <div class="chapter-text">
            <p v-for="(para, i) in paragraphs" :key="i">{{ para }}</p>
          </div>
          <div class="chapter-meta">本章 {{ chapter.word_count }} 字</div>

          <!-- 翻页 -->
          <div class="pager">
            <button
              class="btn-page"
              :disabled="!chapter.has_prev"
              @click="chapter.has_prev && gotoChapter(chapter.prev_index!)"
            >
              ← 上一章
            </button>
            <button class="btn-text" @click="catalogOpen = true">目录</button>
            <button
              class="btn-page"
              :disabled="!chapter.has_next"
              @click="chapter.has_next && gotoChapter(chapter.next_index!)"
            >
              下一章 →
            </button>
          </div>
        </article>

        <!-- 试读边界：注册引导 -->
        <div v-if="needLogin" class="gate-card">
          <div class="gate-icon">🔓</div>
          <h2>登录后继续阅读全书</h2>
          <p>
            《{{ meta.title }}》共 {{ meta.chapter_count }} 章，
            当前为匿名试读。注册平台账号即可阅读全部章节（开源版注册即会员）。
          </p>
          <button class="btn-cta-large" @click="goLogin">立即注册 / 登录</button>
          <p class="gate-hint">注册需有效邀请码，向本书作者或站点管理员索取</p>
        </div>

        <!-- 书籍信息卡（首页） -->
        <article v-if="!chapter && !needLogin" class="book-card">
          <h1 class="book-title">{{ meta.title }}</h1>
          <div class="book-tags">
            <span v-if="meta.genre" class="tag">{{ meta.genre }}</span>
            <span class="tag">{{ meta.chapter_count }} 章</span>
            <span class="tag">{{ formatWords(meta.word_count) }}</span>
          </div>
          <p class="book-intro">{{ meta.intro || '（作者暂未填写简介）' }}</p>
          <button
            class="btn-cta-large"
            @click="catalog?.chapters[0] && selectChapter(0, catalog.chapters[0].readable)"
          >
            开始阅读
          </button>
          <div class="book-stats">浏览 {{ meta.view_count }} · 阅读 {{ meta.read_count }}</div>
        </article>
      </main>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  fetchCatalog,
  fetchChapter,
  fetchShareMeta,
  NeedLoginError,
  type CatalogChapter,
  type ChapterContent,
  type ShareMeta,
} from '@/api/reader'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const shareId = computed(() => String(route.params.shareId || ''))
const meta = ref<ShareMeta | null>(null)
const catalog = ref<{ total: number; trial_chapter_count: number; authenticated: boolean; chapters: CatalogChapter[] } | null>(null)
const chapter = ref<ChapterContent | null>(null)
const currentIndex = ref(0)
const loading = ref(true)
const notFound = ref(false)
const needLogin = ref(false)
const catalogOpen = ref(false)

const paragraphs = computed(() =>
  chapter.value ? chapter.value.content.split('\n').map((p) => p.trim()).filter(Boolean) : [],
)

async function loadAll(sid: string, startChapter?: number) {
  loading.value = true
  notFound.value = false
  try {
    const [m, c] = await Promise.all([fetchShareMeta(sid), fetchCatalog(sid)])
    meta.value = m
    catalog.value = c
    const first = c.chapters[0]
    if (first) {
      const idx = startChapter ?? first.chapter_index
      await selectChapter(idx, c.chapters.some((x) => x.chapter_index === idx && x.readable) || first.readable)
    }
  } catch (e: any) {
    if (e?.response?.status === 404) {
      notFound.value = true
    } else {
      notFound.value = true
    }
  } finally {
    loading.value = false
  }
}

async function gotoChapter(index: number) {
  await selectChapter(index, true)
}

async function selectChapter(index: number, readable: boolean) {
  catalogOpen.value = false
  needLogin.value = false
  if (!readable) {
    currentIndex.value = index
    chapter.value = null
    needLogin.value = true
    return
  }
  try {
    chapter.value = await fetchChapter(shareId.value, index)
    currentIndex.value = index
    window.scrollTo({ top: 0 })
  } catch (e) {
    if (e instanceof NeedLoginError) {
      chapter.value = null
      needLogin.value = true
      currentIndex.value = index
    } else {
      throw e
    }
  }
}

function goLogin() {
  router.push({ path: '/login', query: { redirect: route.fullPath } })
}

function formatWords(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)} 万字`
  return `${n} 字`
}

watch(
  () => route.params.shareId,
  (sid) => {
    if (sid) {
      chapter.value = null
      needLogin.value = false
      loadAll(String(sid))
    }
  },
)

onMounted(async () => {
  await authStore.init()
  await loadAll(shareId.value)
})
</script>

<style scoped lang="scss">
.reader-page {
  min-height: 100vh;
  background: var(--bg-void);
  color: var(--text-primary);
}

.reader-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--bg-glass, rgba(255, 255, 255, 0.85));
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-default);

  .header-inner {
    max-width: 860px;
    margin: 0 auto;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
}

.brand {
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--accent-ember);
  text-decoration: none;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-badge {
  font-size: var(--fs-xs, 11px);
  color: var(--accent-jade);
  border: 1px solid var(--accent-jade);
  border-radius: 999px;
  padding: 2px 10px;
}

.btn-text {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-family: var(--font-ui);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;

  &:hover {
    color: var(--accent-ember);
  }
}

.btn-cta {
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 7px 16px;
  font-family: var(--font-ui);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(217, 119, 6, 0.3);
}

.reader-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 20px 80px;
}

.chapter-card,
.book-card,
.gate-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 12px;
  padding: 36px 32px;
  box-shadow: var(--shadow-md);
}

.chapter-heading {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 500;
  text-align: center;
  margin: 0 0 32px;
}

.chapter-text {
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.9;

  p {
    margin: 0 0 1em;
    text-indent: 2em;
  }
}

.chapter-meta {
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 32px;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border-muted);
}

.btn-page {
  background: none;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--text-primary);
  font-family: var(--font-ui);
  font-size: 13px;
  cursor: pointer;

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  &:not(:disabled):hover {
    border-color: var(--accent-ember);
    color: var(--accent-ember);
  }
}

.book-card {
  text-align: center;

  .book-title {
    font-family: var(--font-display);
    font-size: 32px;
    margin: 0 0 16px;
  }

  .book-tags {
    display: flex;
    gap: 8px;
    justify-content: center;
    margin-bottom: 24px;
  }

  .tag {
    font-size: 12px;
    color: var(--accent-ember);
    background: var(--accent-ember-dim);
    border-radius: 999px;
    padding: 3px 12px;
  }

  .book-intro {
    font-family: var(--font-serif);
    font-size: 15px;
    line-height: 1.9;
    color: var(--text-secondary);
    text-align: left;
    white-space: pre-wrap;
  }

  .book-stats {
    margin-top: 20px;
    color: var(--text-muted);
    font-size: 12px;
  }
}

.btn-cta-large {
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 13px 40px;
  font-family: var(--font-ui);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 12px;
  box-shadow: 0 4px 16px rgba(217, 119, 6, 0.35);
}

.gate-card {
  text-align: center;

  .gate-icon {
    font-size: 36px;
    margin-bottom: 8px;
  }

  h2 {
    font-family: var(--font-display);
    font-weight: 500;
    margin: 0 0 12px;
  }

  p {
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.8;
    max-width: 480px;
    margin: 0 auto 16px;
  }

  .gate-hint {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.btn-cta-inline {
  color: var(--accent-ember);
  text-decoration: none;
  font-size: 14px;
}

.catalog-panel {
  position: fixed;
  top: 57px;
  right: 0;
  bottom: 0;
  width: 320px;
  max-width: 86vw;
  background: var(--bg-surface);
  border-left: 1px solid var(--border-default);
  box-shadow: var(--shadow-deep);
  z-index: 15;
  overflow-y: auto;
  padding: 20px;
}

.catalog-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;

  .catalog-meta {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.catalog-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.catalog-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 11px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 14px;

  &:hover {
    background: var(--bg-elevated);
  }

  &.active {
    color: var(--accent-ember);
    background: var(--accent-ember-dim);
  }

  &.locked {
    color: var(--text-muted);
  }

  .chapter-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .lock-icon {
    font-size: 12px;
    flex-shrink: 0;
  }
}

.state-row,
.state-box {
  max-width: 720px;
  margin: 80px auto;
  text-align: center;
  color: var(--text-secondary);
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(40px);
  opacity: 0;
}

@media (max-width: 600px) {
  .reader-main {
    padding: 20px 14px 60px;
  }
  .chapter-card,
  .book-card,
  .gate-card {
    padding: 24px 18px;
  }
  .chapter-text {
    font-size: 16px;
  }
}
</style>
