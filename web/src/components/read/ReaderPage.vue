<template>
  <div class="reader-page">
    <!-- Loading -->
    <div v-if="loading" class="reader-loading">
      <span class="loading-dot"></span>
      加载中…
    </div>

    <!-- Share not found / disabled -->
    <div v-else-if="notFound" class="reader-empty">
      <div class="empty-icon">📖</div>
      <h2>分享不存在或已关闭</h2>
      <p>作者可能已停止分享这本书。</p>
      <RouterLink to="/" class="btn-back">返回首页</RouterLink>
    </div>

    <!-- Network / server error -->
    <div v-else-if="loadError" class="reader-empty">
      <div class="empty-icon">⚠️</div>
      <h2>加载失败</h2>
      <p>网络异常或服务暂不可用，请稍后重试。</p>
      <button class="btn-back" @click="init()">重试</button>
    </div>

    <template v-else>
      <!-- Top bar -->
      <header class="reader-bar">
        <RouterLink to="/" class="bar-brand">WorldNovel</RouterLink>
        <span class="bar-title">{{ meta?.title }}</span>
        <div class="bar-actions">
          <button
            v-if="authStore.isAuthenticated"
            class="bar-btn"
            :class="{ 'is-active': inBookshelf }"
            @click="toggleBookshelf"
          >
            {{ inBookshelf ? '已加入书架' : '加入书架' }}
          </button>
          <button v-else class="bar-btn bar-btn--primary" @click="goLogin">
            注册 / 登录
          </button>
        </div>
      </header>

      <!-- Book cover / intro -->
      <section v-if="!currentChapter" class="book-cover">
        <div class="cover-card">
          <div class="cover-art">
            <span class="cover-glyph">文</span>
          </div>
          <h1 class="book-title">{{ meta?.title }}</h1>
          <p class="book-intro">{{ meta?.intro || '暂无简介' }}</p>
          <div class="book-meta">
            <span>共 {{ toc?.chapters.length || 0 }} 章</span>
            <span v-if="!hasFullAccess">
              免费试读 {{ toc?.trial_chapters || 0 }} 章 · 注册后阅读全文
            </span>
            <span v-else>已解锁全文</span>
          </div>
          <button class="btn-read" @click="startReading">
            {{ progressChapter > 0 ? `继续阅读 第${progressChapter + 1}章` : '开始阅读' }}
          </button>
        </div>
      </section>

      <!-- Chapter body -->
      <main v-else class="chapter-view">
        <article class="chapter-article">
          <h2 class="chapter-title">
            第{{ chapterIndex + 1 }}章 · {{ chapter?.title || '未命名' }}
          </h2>
          <div class="chapter-body" v-if="chapter">
            <p v-for="(para, i) in paragraphs" :key="i">{{ para }}</p>
          </div>

          <!-- Trial gate shown at the end of the last free chapter -->
          <div v-if="showTrialGate" class="trial-gate">
            <div class="gate-line"></div>
            <p class="gate-text">试读结束</p>
            <p class="gate-sub">注册账号即可免费阅读全文，无需付费</p>
            <button class="btn-read" @click="goLogin">注册后继续阅读</button>
          </div>

          <div class="chapter-nav">
            <button :disabled="chapterIndex <= 0" @click="goto(chapterIndex - 1)">
              上一章
            </button>
            <button class="nav-toc" @click="tocOpen = true">目录</button>
            <button
              :disabled="chapterIndex >= (toc?.chapters.length || 1) - 1"
              @click="goto(chapterIndex + 1)"
            >
              下一章
            </button>
          </div>
        </article>
      </main>

      <!-- TOC drawer -->
      <transition name="fade">
        <div v-if="tocOpen" class="toc-scrim" @click.self="tocOpen = false">
          <aside class="toc-panel">
            <div class="toc-head">
              <h3>目录</h3>
              <button class="toc-close" @click="tocOpen = false">✕</button>
            </div>
            <ul class="toc-list">
              <li
                v-for="ch in toc?.chapters"
                :key="ch.chapter_index"
                class="toc-item"
                :class="{
                  'is-current': currentChapter && ch.chapter_index === chapterIndex,
                  'is-locked': !ch.readable,
                }"
                @click="onTocClick(ch)"
              >
                <span class="toc-name">
                  第{{ ch.chapter_index + 1 }}章 {{ ch.title }}
                </span>
                <span v-if="!ch.readable" class="toc-lock">🔒</span>
              </li>
            </ul>
          </aside>
        </div>
      </transition>

      <!-- Register CTA modal (locked chapter clicked) -->
      <transition name="fade">
        <div v-if="loginPrompt" class="modal-scrim" @click.self="loginPrompt = false">
          <div class="modal-card">
            <h3>注册即可阅读全文</h3>
            <p>
              试读章节已结束。注册一个账号即可免费阅读全部内容 —
              开源版不收费、无付费墙。
            </p>
            <div class="modal-actions">
              <button class="btn-ghost" @click="loginPrompt = false">稍后再说</button>
              <button class="btn-read" @click="goLogin">前往注册 / 登录</button>
            </div>
          </div>
        </div>
      </transition>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  getSharePage,
  getShareToc,
  getShareChapter,
  reportConversion,
  updateBookshelf,
  getMyProgress,
  type ShareMeta,
  type ShareToc,
  type ChapterBody,
  type ShareChapterItem,
} from '@/api/share'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const shareId = computed(() => String(route.params.shareId || ''))
const chapterIndex = computed(() => {
  const raw = route.params.chapterIndex
  return raw === undefined || raw === '' ? -1 : Number(raw)
})
const currentChapter = computed(() => chapterIndex.value >= 0)

const loading = ref(true)
const notFound = ref(false)
const loadError = ref(false)
const meta = ref<ShareMeta | null>(null)
const toc = ref<ShareToc | null>(null)
const chapter = ref<ChapterBody | null>(null)
const tocOpen = ref(false)
const loginPrompt = ref(false)
const inBookshelf = ref(false)
const progressChapter = ref(0)

const hasFullAccess = computed(() => toc.value?.has_full_access === true)

const paragraphs = computed(() =>
  (chapter.value?.content || '')
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean),
)

// Show the gate right after the last readable chapter for anonymous visitors
const showTrialGate = computed(() => {
  if (!toc.value || hasFullAccess.value) return false
  const trial = toc.value.trial_chapters
  return chapterIndex.value === trial - 1
})

function goLogin() {
  const redirect = `/read/${shareId.value}`
  router.push({
    name: 'login',
    query: { redirect, from_share: shareId.value },
  })
}

async function loadMetaAndToc() {
  const [{ data: m }, { data: t }] = await Promise.all([
    getSharePage(shareId.value),
    getShareToc(shareId.value),
  ])
  meta.value = m
  toc.value = t
}

async function loadChapter(idx: number) {
  chapter.value = null
  try {
    const { data } = await getShareChapter(shareId.value, idx)
    chapter.value = data
    // Registered readers sync progress automatically (also done server-side)
  } catch (e: any) {
    const detail = e.response?.data?.detail
    const code = typeof detail === 'object' ? detail?.code : ''
    if (e.response?.status === 403 && code === 'need_login') {
      loginPrompt.value = true
      // Fall back to the book cover view
      router.replace({ name: 'read', params: { shareId: shareId.value } })
    } else if (e.response?.status === 404) {
      notFound.value = true
    }
  }
}

async function loadProgress() {
  if (!authStore.isAuthenticated) return
  try {
    const { data } = await getMyProgress(shareId.value)
    progressChapter.value = data.chapter_index || 0
    inBookshelf.value = !!data.in_bookshelf
  } catch {
    // ignore
  }
}

async function fireConversionOnce() {
  // After login redirect back with ?from_share=..., record conversion (idempotent)
  const fromShare = route.query.from_share
  if (!authStore.isAuthenticated || !fromShare) return
  const flag = `wn_conversion_${fromShare}`
  if (sessionStorage.getItem(flag)) return
  try {
    await reportConversion(String(fromShare))
    sessionStorage.setItem(flag, '1')
  } catch {
    // non-fatal
  }
}

function startReading() {
  const target = hasFullAccess.value && progressChapter.value > 0
    ? progressChapter.value
    : 0
  goto(Math.min(target, (toc.value?.chapters.length || 1) - 1))
}

function goto(idx: number) {
  const chapters = toc.value?.chapters || []
  if (idx < 0 || idx >= chapters.length) return
  const ch = chapters[idx]
  if (!ch.readable) {
    loginPrompt.value = true
    return
  }
  tocOpen.value = false
  loginPrompt.value = false
  router.push({
    name: 'read-chapter',
    params: { shareId: shareId.value, chapterIndex: String(idx) },
  })
}

function onTocClick(ch: ShareChapterItem) {
  if (!ch.readable) {
    loginPrompt.value = true
    return
  }
  goto(ch.chapter_index)
}

async function toggleBookshelf() {
  if (!meta.value) return
  inBookshelf.value = !inBookshelf.value
  try {
    await updateBookshelf(meta.value.novel_id, inBookshelf.value, shareId.value)
  } catch {
    inBookshelf.value = !inBookshelf.value
  }
}

async function init() {
  loading.value = true
  notFound.value = false
  try {
    await loadMetaAndToc()
    await loadProgress()
    await fireConversionOnce()
    if (currentChapter.value) {
      await loadChapter(chapterIndex.value)
    }
  } catch (e: any) {
    if (e.response?.status === 404) {
      notFound.value = true
    } else {
      // 网络错误/服务器错误：不当作"分享不存在"，提示重试
      loadError.value = true
    }
  } finally {
    loading.value = false
  }
}

onMounted(init)

// Re-init when navigating between cover/chapters or after auth changes
watch([shareId, chapterIndex], (prev, next) => {
  if (prev[0] !== next[0]) {
    init()
  } else if (prev[1] !== next[1]) {
    if (currentChapter.value) loadChapter(chapterIndex.value)
    else chapter.value = null
  }
})

watch(
  () => authStore.isAuthenticated,
  async (authed) => {
    if (authed && toc.value) {
      // Freshly registered/logged-in — refresh TOC so locks disappear
      try {
        const { data } = await getShareToc(shareId.value)
        toc.value = data
        await fireConversionOnce()
        if (currentChapter.value) await loadChapter(chapterIndex.value)
      } catch {
        // ignore
      }
    }
  },
)
</script>

<style scoped lang="scss">
.reader-page {
  min-height: 100vh;
  background: var(--bg-void);
  color: var(--text-primary);
}

.reader-loading,
.reader-empty {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-sm);
  color: var(--text-secondary);

  .empty-icon {
    font-size: 40px;
  }

  .btn-back {
    margin-top: var(--sp-md);
    color: var(--accent-ember);
  }
}

.loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-ember);
  animation: pulse 1s infinite alternate;
}

@keyframes pulse {
  from { opacity: 0.3; }
  to { opacity: 1; }
}

// ── Top bar ──────────────────────────────────────────
.reader-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  padding: 10px var(--sp-md);
  background: var(--bg-glass);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border-muted);

  .bar-brand {
    font-weight: 700;
    color: var(--accent-ember);
    text-decoration: none;
    flex-shrink: 0;
  }

  .bar-title {
    flex: 1;
    text-align: center;
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bar-btn {
    flex-shrink: 0;
    border: 1px solid var(--border-default);
    background: var(--bg-surface);
    color: var(--text-secondary);
    font-size: var(--fs-sm);
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--duration-fast);

    &.is-active {
      border-color: var(--border-active);
      color: var(--accent-ember);
    }

    &--primary {
      background: var(--accent-ember);
      border-color: var(--accent-ember);
      color: #fff;
    }
  }
}

// ── Cover ────────────────────────────────────────────
.book-cover {
  display: flex;
  justify-content: center;
  padding: var(--sp-2xl) var(--sp-md);
}

.cover-card {
  max-width: 640px;
  width: 100%;
  text-align: center;
}

.cover-art {
  width: 180px;
  height: 240px;
  margin: 0 auto var(--sp-lg);
  border-radius: var(--radius-sm);
  background: linear-gradient(145deg, #1c1917, #431407);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-deep);

  .cover-glyph {
    font-family: var(--font-serif);
    font-size: 64px;
    color: var(--accent-ember);
    opacity: 0.9;
  }
}

.book-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  margin: 0 0 var(--sp-md);
}

.book-intro {
  color: var(--text-secondary);
  line-height: 1.8;
  white-space: pre-line;
  margin: 0 auto var(--sp-md);
  max-width: 520px;
}

.book-meta {
  display: flex;
  justify-content: center;
  gap: var(--sp-md);
  flex-wrap: wrap;
  color: var(--text-muted);
  font-size: var(--fs-sm);
  margin-bottom: var(--sp-lg);
}

.btn-read {
  background: var(--accent-ember);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--fs-md);
  padding: 12px 32px;
  cursor: pointer;
  transition: transform var(--duration-fast);

  &:hover {
    transform: translateY(-1px);
  }
}

// ── Chapter view ─────────────────────────────────────
.chapter-view {
  display: flex;
  justify-content: center;
  padding: var(--sp-xl) var(--sp-md) var(--sp-4xl);
}

.chapter-article {
  max-width: 680px;
  width: 100%;
}

.chapter-title {
  font-family: var(--font-display);
  font-size: var(--fs-lg);
  text-align: center;
  margin: var(--sp-md) 0 var(--sp-xl);
}

.chapter-body {
  font-family: var(--font-serif);
  font-size: var(--fs-md);
  line-height: 1.9;
  color: var(--text-primary);

  p {
    margin: 0 0 1em;
    text-indent: 2em;
  }
}

.trial-gate {
  margin: var(--sp-2xl) 0;
  text-align: center;

  .gate-line {
    width: 60px;
    height: 1px;
    background: var(--border-default);
    margin: 0 auto var(--sp-md);
  }

  .gate-text {
    font-size: var(--fs-md);
    margin: 0 0 var(--sp-xs);
  }

  .gate-sub {
    color: var(--text-muted);
    font-size: var(--fs-sm);
    margin: 0 0 var(--sp-md);
  }
}

.chapter-nav {
  display: flex;
  justify-content: space-between;
  gap: var(--sp-sm);
  margin-top: var(--sp-2xl);
  border-top: 1px solid var(--border-muted);
  padding-top: var(--sp-md);

  button {
    flex: 1;
    padding: 10px;
    border: 1px solid var(--border-default);
    background: var(--bg-surface);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    cursor: pointer;
    font-size: var(--fs-sm);

    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }

    &.nav-toc {
      flex: 0.6;
    }
  }
}

// ── TOC drawer ───────────────────────────────────────
.toc-scrim {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 50;
  display: flex;
  justify-content: flex-end;
}

.toc-panel {
  width: min(360px, 85vw);
  height: 100%;
  background: var(--bg-surface);
  box-shadow: var(--shadow-deep);
  display: flex;
  flex-direction: column;
}

.toc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-md);
  border-bottom: 1px solid var(--border-muted);

  h3 {
    margin: 0;
    font-size: var(--fs-base);
  }

  .toc-close {
    border: none;
    background: none;
    cursor: pointer;
    color: var(--text-muted);
    font-size: var(--fs-base);
  }
}

.toc-list {
  list-style: none;
  margin: 0;
  padding: var(--sp-sm);
  overflow-y: auto;
  flex: 1;
}

.toc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-sm);
  padding: 10px var(--sp-sm);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--fs-sm);
  color: var(--text-secondary);

  &:hover {
    background: var(--bg-elevated);
  }

  &.is-current {
    color: var(--accent-ember);
    background: var(--accent-ember-dim);
  }

  &.is-locked .toc-name {
    color: var(--text-muted);
  }

  .toc-lock {
    font-size: 12px;
    opacity: 0.7;
  }
}

// ── Modal ────────────────────────────────────────────
.modal-scrim {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-md);
}

.modal-card {
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-deep);
  padding: var(--sp-xl);
  max-width: 380px;
  width: 100%;
  text-align: center;

  h3 {
    margin: 0 0 var(--sp-sm);
  }

  p {
    color: var(--text-secondary);
    font-size: var(--fs-sm);
    line-height: 1.7;
    margin: 0 0 var(--sp-md);
  }

  .modal-actions {
    display: flex;
    gap: var(--sp-sm);
    justify-content: center;
  }

  .btn-ghost {
    border: 1px solid var(--border-default);
    background: none;
    color: var(--text-secondary);
    padding: 10px 18px;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-base);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
