<template>
  <div class="reader-page">
    <!-- Invalid / closed share -->
    <div v-if="notFound" class="reader-dead">
      <div class="dead-card">
        <h2>分享不存在或已关闭</h2>
        <p>作者可能已关闭该分享链接。</p>
        <a class="dead-home" href="/">返回 WorldNovel</a>
      </div>
    </div>

    <template v-else>
      <!-- Top bar -->
      <header class="reader-header">
        <button class="icon-btn" @click="tocOpen = true" aria-label="目录">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
        <span class="reader-title">{{ meta?.title || '加载中…' }}</span>
        <span v-if="meta?.authed" class="reader-badge">已注册 · 全文</span>
      </header>

      <main class="reader-main">
        <!-- Book intro (chapter -1) -->
        <article v-if="currentIndex === -1" class="book-intro">
          <div class="book-cover" aria-hidden="true">
            <span>{{ meta?.title?.slice(0, 1) || '书' }}</span>
          </div>
          <h1 class="book-title">{{ meta?.title }}</h1>
          <p class="book-genre">{{ meta?.genre }}</p>
          <p v-if="meta?.stats.views" class="book-meta font-data">{{ meta.stats.views }} 次访问</p>
          <h3 v-if="meta?.intro" class="intro-label">简介</h3>
          <p v-if="meta?.intro" class="book-intro-text">{{ meta.intro }}</p>
          <button
            class="start-btn"
            :disabled="!toc.length"
            @click="gotoChapter(firstReadable)"
          >
            {{ meta?.authed || trialOpen === 0 ? '开始阅读' : `试读前 ${trialOpen} 章` }}
          </button>
        </article>

        <!-- Chapter content -->
        <article v-else-if="chapter" class="chapter-body">
          <h1 class="chapter-title">第{{ chapter.index + 1 }}章 {{ chapter.title.replace(/^第.+?章\s*/, '') }}</h1>
          <div class="chapter-text">
            <p v-for="(p, i) in paragraphs" :key="i">{{ p }}</p>
          </div>
        </article>

        <!-- Locked chapter -->
        <div v-else-if="rateLimited" class="locked-card">
          <h2>请求过于频繁</h2>
          <p>触发了阅读接口限流，请稍后再试。</p>
        </div>

        <div v-else-if="chapterMissing" class="locked-card">
          <h2>章节不存在</h2>
          <p>该章节尚未生成或已被移除。</p>
        </div>

        <div v-else-if="locked" class="locked-card">
          <div class="lock-icon">&#128274;</div>
          <h2>注册后阅读全部章节</h2>
          <p>
            本书开放试读
            <template v-if="meta?.trial_mode === 'first_n_chapters'">前 {{ meta.trial_value }} 章</template>
            <template v-else-if="meta?.trial_mode === 'ratio'">{{ meta.trial_value }}% 内容</template>
            <template v-else-if="meta?.trial_mode === 'word_count'">{{ meta.trial_value.toLocaleString() }} 字</template>
            <template v-else>部分章节</template>
            ，注册（邀请码）后立即解锁全书，免费阅读。
          </p>

          <!-- jwt mode: invite code directly -->
          <div v-if="authMode === 'jwt'" class="login-box">
            <input
              v-model="inviteCode"
              class="invite-input"
              type="text"
              placeholder="输入邀请码"
              @keyup.enter="doLogin"
            />
            <button class="start-btn" :disabled="loggingIn" @click="doLogin">
              {{ loggingIn ? '验证中…' : '注册 / 登录并解锁' }}
            </button>
            <p v-if="loginError" class="login-error">{{ loginError }}</p>
            <p v-else-if="!hasReaderToken" class="login-hint">开源版邀请码即账号，无需额外注册流程</p>
          </div>

          <!-- casdoor mode: redirect to sidecar OAuth -->
          <a v-else-if="authMode === 'casdoor' && oauthUrl" class="start-btn link-btn" :href="oauthUrl">
            使用账号登录
          </a>
        </div>

        <div v-else class="loading-hint">加载中…</div>

        <!-- Footer nav -->
        <nav v-if="chapter" class="chapter-nav">
          <button
            class="nav-btn"
            :disabled="!chapter.has_prev && currentIndex <= 0"
            @click="prevChapter"
          >上一章</button>
          <button class="nav-btn toc-btn" @click="tocOpen = true">目录</button>
          <button
            class="nav-btn"
            :disabled="!chapter.has_next"
            @click="nextChapter"
          >{{ chapter.next_readable === false ? '注册解锁下一章' : '下一章' }}</button>
        </nav>
      </main>

      <!-- TOC drawer -->
      <div v-if="tocOpen" class="toc-mask" @click.self="tocOpen = false">
        <aside class="toc-drawer">
          <div class="toc-head">
            <span>目录</span>
            <button class="icon-btn" @click="tocOpen = false" aria-label="关闭">✕</button>
          </div>
          <ul class="toc-list">
            <li class="toc-intro" :class="{ active: currentIndex === -1 }" @click="gotoChapter(-1)">
              简介
            </li>
            <li
              v-for="c in toc"
              :key="c.index"
              class="toc-item"
              :class="{ active: c.index === currentIndex, locked: !c.readable }"
              @click="c.readable ? gotoChapter(c.index) : (lockedIndex = c.index, tocOpen = false)"
            >
              <span class="toc-chapter-title">{{ c.title }}</span>
              <span v-if="!c.readable" class="toc-lock">🔒</span>
            </li>
          </ul>
        </aside>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  fetchShareMeta, fetchToc, fetchChapter, readerLogin, fetchAuthConfig,
  type ReaderMeta, type TocChapter, type ChapterContent,
} from '@/api/share'
import { readerToken, setReaderToken } from '@/api/public'

const route = useRoute()
const shareId = route.params.shareId as string

const notFound = ref(false)
const meta = ref<ReaderMeta | null>(null)
const toc = ref<TocChapter[]>([])
const chapter = ref<ChapterContent | null>(null)
const currentIndex = ref(-1)
const locked = ref(false)
const lockedIndex = ref<number | null>(null)
const rateLimited = ref(false)
const chapterMissing = ref(false)
const tocOpen = ref(false)

const authMode = ref('jwt')
const oauthUrl = ref('')
const inviteCode = ref('')
const loggingIn = ref(false)
const loginError = ref('')
const hasReaderToken = ref(!!readerToken())

const paragraphs = computed(() => (chapter.value?.content || '').split(/\n+/).filter((p) => p.trim()))

const firstReadable = computed(() => toc.value.find((c) => c.readable)?.index ?? 0)

const trialOpen = computed(() => meta.value?.trial_open_chapters ?? 0)

async function loadInitial() {
  notFound.value = false
  try {
    meta.value = await fetchShareMeta(shareId)
    toc.value = await fetchToc(shareId)
    // Resume progress for returning registered readers
    let start = -1
    if (meta.value.authed) {
      start = -1 // 已注册读者也从简介页开始；点击"开始阅读"即可
    }
    currentIndex.value = start
    chapter.value = null
  } catch (e: any) {
    if (e.response?.status === 404) notFound.value = true
  }
}

function resetChapterState() {
  chapter.value = null
  locked.value = false
  rateLimited.value = false
  chapterMissing.value = false
}

async function gotoChapter(index: number) {
  if (index < 0) {
    currentIndex.value = -1
    resetChapterState()
    tocOpen.value = false
    window.scrollTo({ top: 0 })
    return
  }
  try {
    chapter.value = await fetchChapter(shareId, index)
    currentIndex.value = index
    locked.value = false
    rateLimited.value = false
    chapterMissing.value = false
    lockedIndex.value = null
    tocOpen.value = false
    window.scrollTo({ top: 0 })
  } catch (e: any) {
    const status = e.response?.status
    if (status === 403 && e.response.data?.code === 'need_login') {
      resetChapterState()
      currentIndex.value = index
      locked.value = true
      lockedIndex.value = index
      tocOpen.value = false
      window.scrollTo({ top: 0 })
    } else if (status === 429) {
      resetChapterState()
      rateLimited.value = true
    } else if (status === 404) {
      // Meta already loaded successfully → it's the chapter that's missing,
      // not the whole share (which must keep serving other chapters).
      if (meta.value) {
        resetChapterState()
        chapterMissing.value = true
      } else {
        notFound.value = true
      }
    }
  }
}

function prevChapter() {
  if (currentIndex.value <= 0) return gotoChapter(-1)
  gotoChapter(currentIndex.value - 1)
}

async function nextChapter() {
  if (!chapter.value) return
  if (chapter.value.next_readable === false) {
    // 下一章超出试读 → 注册引导
    currentIndex.value = chapter.value.index + 1
    const nextIdx = chapter.value.index + 1
    resetChapterState()
    locked.value = true
    lockedIndex.value = nextIdx
    return
  }
  await gotoChapter(chapter.value.index + 1)
}

async function doLogin() {
  loginError.value = ''
  if (!inviteCode.value.trim()) {
    loginError.value = '请输入邀请码'
    return
  }
  loggingIn.value = true
  try {
    const res = await readerLogin(inviteCode.value.trim())
    setReaderToken(res.access_token)
    hasReaderToken.value = true
    // 刷新权限视图
    meta.value = await fetchShareMeta(shareId)
    toc.value = await fetchToc(shareId)
    await gotoChapter(lockedIndex.value ?? currentIndex.value)
  } catch (e: any) {
    loginError.value = e.response?.status === 401
      ? '邀请码无效或已达使用上限'
      : '登录失败，请稍后再试'
  } finally {
    loggingIn.value = false
  }
}

onMounted(async () => {
  try {
    const cfg = await fetchAuthConfig()
    authMode.value = cfg.mode
    oauthUrl.value = cfg.oauth_login_url || ''
  } catch { /* defaults to jwt */ }
  await loadInitial()
})

watch(() => route.params.shareId, (val) => {
  if (val && val !== shareId) window.location.reload()
})
</script>

<style scoped lang="scss">
.reader-page {
  min-height: 100vh;
  background: var(--bg-void);
  color: var(--text-primary);
  font-family: var(--font-ui);
}

.reader-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  height: 48px;
  padding: 0 var(--sp-md);
  background: var(--bg-glass, rgba(255,255,255,0.85));
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border-default);
}

.reader-title {
  flex: 1;
  font-size: var(--fs-sm);
  font-weight: 550;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reader-badge {
  font-size: var(--fs-xs);
  color: var(--accent-jade);
  border: 1px solid rgba(5,150,105,0.3);
  padding: 1px 8px;
  border-radius: var(--radius-badge);
}

.icon-btn {
  display: inline-flex;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
}

.reader-main {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--sp-lg) var(--sp-md) 64px;
}

// Intro
.book-intro {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--sp-xl) 0;
}

.book-cover {
  width: 120px;
  height: 160px;
  border-radius: var(--radius-md);
  background: linear-gradient(160deg, #27272a, #1a1a1f);
  border: 1px solid var(--accent-ember);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--sp-lg);

  span {
    font-family: var(--font-serif);
    font-size: 44px;
    color: var(--accent-ember);
  }
}

.book-title {
  font-family: var(--font-serif);
  font-size: var(--fs-xl);
  margin: 0 0 var(--sp-xs);
}

.book-genre { color: var(--text-muted); font-size: var(--fs-sm); margin: 0 0 var(--sp-xs); }
.book-meta { color: var(--text-muted); font-size: var(--fs-xs); margin: 0; }

.intro-label {
  width: 100%;
  text-align: left;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin: var(--sp-lg) 0 var(--sp-xs);
}

.book-intro-text {
  width: 100%;
  text-align: left;
  font-family: var(--font-serif);
  font-size: var(--fs-md);
  line-height: 1.9;
  color: var(--text-secondary);
  white-space: pre-wrap;
}

// Chapter
.chapter-title {
  font-family: var(--font-serif);
  font-size: var(--fs-lg);
  text-align: center;
  margin: var(--sp-md) 0 var(--sp-lg);
}

.chapter-text p {
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.95;
  text-indent: 2em;
  margin: 0 0 0.6em;
}

.chapter-nav {
  display: flex;
  justify-content: space-between;
  gap: var(--sp-sm);
  margin-top: var(--sp-xl);
}

.nav-btn {
  flex: 1;
  height: 40px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  cursor: pointer;

  &:disabled { opacity: 0.4; cursor: not-allowed; }
  &:not(:disabled):hover { border-color: var(--accent-ember); color: var(--accent-ember); }
}

.toc-btn { flex: 0 0 96px; }

// Locked
.locked-card {
  text-align: center;
  padding: var(--sp-2xl) var(--sp-md);
  margin-top: var(--sp-xl);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);

  h2 { font-size: var(--fs-lg); margin: var(--sp-sm) 0; }
  p { color: var(--text-secondary); font-size: var(--fs-sm); line-height: 1.8; }
}

.lock-icon { font-size: 32px; }

.login-box {
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
  max-width: 320px;
  margin: var(--sp-md) auto 0;
}

.invite-input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-void);
  color: var(--text-primary);
  font-size: var(--fs-base);
  text-align: center;
  letter-spacing: 0.08em;

  &:focus { outline: none; border-color: var(--accent-ember); }
}

.start-btn {
  height: 42px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--accent-ember);
  color: #fff;
  font-size: var(--fs-base);
  font-weight: 550;
  cursor: pointer;
  margin-top: var(--sp-sm);
  padding: 0 var(--sp-lg);

  &:hover { background: #b45309; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.link-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  max-width: 320px;
}

.login-error { color: var(--accent-cinnabar) !important; }
.login-hint { font-size: var(--fs-xs) !important; color: var(--text-muted) !important; }

.loading-hint { text-align: center; color: var(--text-muted); padding: var(--sp-2xl); }

// TOC drawer
.toc-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: 100;
  display: flex;
}

.toc-drawer {
  width: min(320px, 84vw);
  height: 100%;
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
}

.toc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-md);
  border-bottom: 1px solid var(--border-default);
  font-weight: 600;
}

.toc-list {
  list-style: none;
  margin: 0;
  padding: var(--sp-sm);
  overflow-y: auto;
}

.toc-intro,
.toc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px var(--sp-sm);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  cursor: pointer;

  &:hover { background: var(--bg-elevated); }
  &.active { color: var(--accent-ember); font-weight: 550; }
  &.locked { color: var(--text-muted); }
}

.toc-chapter-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toc-lock { font-size: var(--fs-xs); margin-left: var(--sp-xs); }

// Dead share
.reader-dead {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-md);
}

.dead-card {
  text-align: center;
  h2 { font-size: var(--fs-lg); }
  p { color: var(--text-secondary); font-size: var(--fs-sm); }
}

.dead-home {
  display: inline-block;
  margin-top: var(--sp-md);
  color: var(--accent-ember);
  font-size: var(--fs-sm);
}
</style>
