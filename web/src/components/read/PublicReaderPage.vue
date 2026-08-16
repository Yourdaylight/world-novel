<template>
  <div class="reader-page" :class="{ 'is-dark': theme.isDark.value }">
    <header class="reader-topbar">
      <router-link to="/" class="brand">WorldNovel</router-link>
      <div class="topbar-actions">
        <button class="icon-btn" :title="theme.isDark.value ? '切换亮色' : '切换暗色'" @click="theme.toggleTheme()">
          <svg v-if="theme.isDark.value" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>
        </button>
        <button v-if="!auth.isAuthenticated" class="login-chip" @click="openRegister">注册 / 登录读全文</button>
        <span v-else class="user-chip">{{ auth.displayName }}</span>
      </div>
    </header>

    <div v-if="loading" class="state-block">
      <span class="spinner" /> 正在翻开书页…
    </div>

    <div v-else-if="notFound" class="state-block">
      <div class="empty-mark">404</div>
      <p>分享不存在或已被作者关闭。</p>
      <router-link to="/" class="back-link">返回首页</router-link>
    </div>

    <div v-else-if="loadError" class="state-block">
      <p>{{ loadError }}</p>
      <button class="nav-btn" @click="load">重试</button>
    </div>

    <div v-else class="reader-shell">
      <!-- Book header -->
      <section class="book-hero">
        <div class="cover" :style="coverStyle">
          <span class="cover-title">{{ meta?.title }}</span>
          <span class="cover-meta">{{ meta?.genre }} · {{ meta?.chapters_total }}章</span>
        </div>
        <div class="book-info">
          <h1 class="book-title">{{ meta?.title }}</h1>
          <p class="book-genre">{{ meta?.genre }}</p>
          <p class="book-intro">{{ meta?.intro || '（作者暂未填写简介）' }}</p>
          <div class="book-stats font-data">
            <span>{{ meta?.chapters_total }} 章</span>
            <span>{{ meta?.view_count }} 次浏览</span>
            <span v-if="auth.isAuthenticated" class="full-tag">已解锁全文</span>
            <span v-else class="trial-tag">试读 {{ trialLabel }}</span>
          </div>
        </div>
      </section>

      <div class="reader-grid">
        <!-- TOC -->
        <aside class="toc-panel">
          <h2 class="panel-label">目录</h2>
          <ul class="toc-list">
            <li
              v-for="ch in toc"
              :key="ch.chapter_index"
              :class="{ active: ch.chapter_index === activeIndex }"
            >
              <button class="toc-item" @click="openChapter(ch.chapter_index)">
                <span class="toc-name">第{{ ch.chapter_index + 1 }}章 {{ ch.title }}</span>
                <svg v-if="!ch.readable" class="lock-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <span v-else class="toc-words font-data">{{ ch.word_count }}</span>
              </button>
            </li>
          </ul>
        </aside>

        <!-- Chapter -->
        <main class="chapter-panel">
          <div v-if="chapterLoading" class="state-block small"><span class="spinner" /></div>
          <template v-else-if="current">
            <NovelReader :chapter="current" />
            <nav class="chapter-nav">
              <button class="nav-btn" :disabled="activeIndex <= 0" @click="openChapter(activeIndex - 1)">上一章</button>
              <button class="nav-btn primary" @click="openChapter(activeIndex + 1)">
                {{ nextReadable ? '下一章' : '注册读后续' }}
              </button>
            </nav>
          </template>
          <div v-else class="state-block small">从左侧目录选择章节开始阅读。</div>
        </main>
      </div>
    </div>

    <!-- Register / login gate -->
    <transition name="fade">
      <div v-if="registerOpen" class="gate-scrim" @click.self="registerOpen = false">
        <div class="gate-card">
          <button class="gate-close" @click="registerOpen = false">×</button>
          <h3>注册后阅读全部章节</h3>
          <p class="gate-sub">开源版邀请码注册即解锁全书，进度自动同步。</p>

          <template v-if="auth.isJwtMode">
            <input
              v-model="inviteCode"
              class="invite-input"
              type="text"
              placeholder="请输入邀请码"
              @keyup.enter="submitRegister"
            />
            <p v-if="registerError" class="gate-error">{{ registerError }}</p>
            <button class="gate-btn" :disabled="auth.loading" @click="submitRegister">
              {{ auth.loading ? '验证中…' : '邀请码注册 / 登录' }}
            </button>
          </template>

          <template v-else>
            <p class="gate-sub">当前接入统一认证中心，点击前往注册 / 登录。</p>
            <button class="gate-btn" @click="auth.login(true)">前往统一认证中心</button>
          </template>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { useAuthStore } from '@/stores/auth'
import NovelReader from '@/components/novel/NovelReader.vue'
import {
  fetchShareChapters,
  fetchShareChapter,
  type ShareMeta,
  type TocChapter,
  type ShareChapter,
} from '@/api/share'
import axios from 'axios'

const route = useRoute()
const theme = useTheme()
const auth = useAuthStore()
const shareId = String(route.params.shareId || '')

const loading = ref(true)
const notFound = ref(false)
const loadError = ref('')
const meta = ref<ShareMeta | null>(null)
const toc = ref<TocChapter[]>([])
const current = ref<ShareChapter | null>(null)
const activeIndex = ref(-1)
const chapterLoading = ref(false)

const registerOpen = ref(false)
const inviteCode = ref('')
const registerError = ref('')

const trialLabel = computed(() => {
  if (!meta.value) return ''
  if (meta.value.trial_mode === 'word_count') return `前 ${meta.value.trial_value} 字`
  if (meta.value.trial_mode === 'ratio') return `前 ${meta.value.trial_value}%`
  return `前 ${meta.value.trial_value} 章`
})

const nextReadable = computed(() => {
  const next = toc.value[activeIndex.value + 1]
  return next ? next.readable : true
})

const coverStyle = computed(() => ({
  background: 'linear-gradient(160deg,#1c1917,#431407)',
}))

async function load() {
  loading.value = true
  await auth.init().catch(() => undefined)
  try {
    const data = await fetchShareChapters(shareId)
    meta.value = data.meta
    toc.value = data.chapters
    notFound.value = false
    if (data.chapters.length) await openChapter(0)
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) {
      notFound.value = true
    } else if (axios.isAxiosError(e) && e.response?.status === 429) {
      loadError.value = '请求过于频繁，请稍后再试。'
    } else {
      loadError.value = '加载失败，请检查网络后刷新。'
    }
  } finally {
    loading.value = false
  }
}

async function openChapter(index: number) {
  const ch = toc.value[index]
  if (!ch) return
  if (!ch.readable) {
    openRegister()
    return
  }
  chapterLoading.value = true
  activeIndex.value = index
  try {
    current.value = await fetchShareChapter(shareId, ch.chapter_index)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    // Token may have been the only thing granting access / expired.
    if (axios.isAxiosError(e) && e.response?.status === 403) {
      ch.readable = false
      openRegister()
      current.value = null
    }
  } finally {
    chapterLoading.value = false
  }
}

function openRegister() {
  registerError.value = ''
  registerOpen.value = true
}

async function submitRegister() {
  registerError.value = ''
  try {
    await auth.loginWithInviteCode(inviteCode.value)
    registerOpen.value = false
    // Refresh TOC readable flags under the new identity, then continue.
    const data = await fetchShareChapters(shareId)
    meta.value = data.meta
    toc.value = data.chapters
    const target = activeIndex.value >= 0 ? activeIndex.value : 0
    current.value = null
    await openChapter(target)
  } catch (e: any) {
    registerError.value = e?.message || '注册失败'
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.reader-page {
  min-height: 100vh;
  background: var(--bg-void);
  color: var(--text-primary);
  font-family: var(--font-ui);
}

.reader-topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-lg);
  height: 56px;
  background: var(--bg-glass);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-default);
}
.brand {
  font-family: var(--font-display);
  font-size: var(--fs-lg);
  color: var(--accent-ember);
  text-decoration: none;
}
.topbar-actions { display: flex; align-items: center; gap: var(--sp-sm); }
.icon-btn {
  display: inline-flex; border: 1px solid var(--border-default); background: transparent;
  color: var(--text-secondary); border-radius: var(--radius-sm);
  width: 34px; height: 34px; align-items: center; justify-content: center; cursor: pointer;
}
.login-chip, .user-chip {
  font-size: var(--fs-sm); font-weight: 600; color: #fff;
  background: var(--accent-ember); border: none; border-radius: var(--radius-sm);
  padding: 7px 14px; cursor: pointer;
}
.user-chip { background: transparent; color: var(--text-secondary); border: 1px solid var(--border-default); }

.reader-shell { max-width: 1080px; margin: 0 auto; padding: var(--sp-lg); }

.book-hero {
  display: flex; gap: var(--sp-lg); align-items: stretch;
  background: var(--bg-surface); border: 1px solid var(--border-default);
  border-radius: var(--radius-lg); padding: var(--sp-lg); box-shadow: var(--shadow-sm);
  margin-bottom: var(--sp-lg);
}
.cover {
  flex: 0 0 132px; height: 180px; border-radius: var(--radius-md);
  display: flex; flex-direction: column; align-items: center; justify-content: space-between;
  padding: var(--sp-md); color: #fafaf9; text-align: center;
}
.cover-title { font-family: var(--font-serif); font-size: var(--fs-md); font-weight: 700; line-height: 1.4; }
.cover-meta { font-size: var(--fs-xs); color: #a8a29e; }
.book-title { font-family: var(--font-display); font-size: var(--fs-xl); font-weight: 400; margin: 0 0 var(--sp-xs); }
.book-genre { color: var(--accent-ember); font-size: var(--fs-sm); margin: 0 0 var(--sp-sm); }
.book-intro { color: var(--text-secondary); font-size: var(--fs-base); line-height: 1.7; margin: 0 0 var(--sp-md); white-space: pre-wrap; }
.book-stats { display: flex; gap: var(--sp-md); font-size: var(--fs-xs); color: var(--text-muted); }
.full-tag { color: var(--accent-jade); }
.trial-tag { color: var(--accent-ember); }

.reader-grid { display: grid; grid-template-columns: 240px 1fr; gap: var(--sp-lg); align-items: start; }
.toc-panel {
  position: sticky; top: 72px;
  background: var(--bg-surface); border: 1px solid var(--border-default);
  border-radius: var(--radius-md); padding: var(--sp-md); max-height: calc(100vh - 96px); overflow: auto;
}
.panel-label { font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin: 0 0 var(--sp-sm); }
.toc-list { list-style: none; margin: 0; padding: 0; }
.toc-item {
  width: 100%; display: flex; align-items: center; justify-content: space-between; gap: var(--sp-xs);
  background: none; border: none; text-align: left; cursor: pointer;
  padding: 7px 8px; border-radius: var(--radius-sm); font-size: var(--fs-sm);
  color: var(--text-secondary);
}
.toc-item:hover { background: var(--accent-ember-dim); color: var(--text-primary); }
.toc-list li.active .toc-item { background: var(--accent-ember-dim); color: var(--accent-ember); font-weight: 600; }
.toc-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toc-words { font-size: 10px; color: var(--text-muted); flex-shrink: 0; }
.lock-icon { color: var(--text-muted); flex-shrink: 0; }

.chapter-panel {
  background: var(--bg-surface); border: 1px solid var(--border-default);
  border-radius: var(--radius-lg); padding: var(--sp-xl); min-height: 320px; box-shadow: var(--shadow-sm);
}
.chapter-nav { display: flex; justify-content: space-between; gap: var(--sp-md); margin-top: var(--sp-xl); max-width: 720px; margin-left: auto; margin-right: auto; }
.nav-btn {
  font-size: var(--fs-sm); padding: 9px 18px; border-radius: var(--radius-md);
  border: 1px solid var(--border-default); background: var(--bg-elevated);
  color: var(--text-primary); cursor: pointer;
  &:disabled { opacity: 0.4; cursor: not-allowed; }
  &.primary { background: var(--accent-ember); border-color: var(--accent-ember); color: #fff; }
}

.state-block {
  display: flex; flex-direction: column; align-items: center; gap: var(--sp-md);
  padding: var(--sp-3xl) var(--sp-lg); color: var(--text-secondary); font-size: var(--fs-base);
  &.small { padding: var(--sp-2xl); }
}
.empty-mark { font-family: var(--font-display); font-size: var(--fs-3xl); color: var(--text-muted); }
.back-link { color: var(--accent-ember); }
.spinner { width: 22px; height: 22px; border: 2px solid var(--border-default); border-top-color: var(--accent-ember); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Register gate */
.gate-scrim {
  position: fixed; inset: 0; z-index: 50; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; padding: var(--sp-md);
}
.gate-card {
  position: relative; width: 100%; max-width: 380px;
  background: var(--bg-surface); border: 1px solid var(--border-default);
  border-radius: var(--radius-lg); padding: var(--sp-xl); box-shadow: var(--shadow-deep);
}
.gate-card h3 { margin: 0 0 var(--sp-xs); font-size: var(--fs-lg); }
.gate-sub { color: var(--text-secondary); font-size: var(--fs-sm); margin: 0 0 var(--sp-lg); line-height: 1.6; }
.gate-close { position: absolute; top: 12px; right: 14px; border: none; background: none; font-size: 22px; color: var(--text-muted); cursor: pointer; }
.invite-input {
  width: 100%; box-sizing: border-box; padding: 11px 14px; margin-bottom: var(--sp-sm);
  border: 1px solid var(--border-default); border-radius: var(--radius-md);
  background: var(--bg-void); color: var(--text-primary); font-size: var(--fs-base);
}
.gate-error { color: var(--accent-cinnabar); font-size: var(--fs-sm); margin: 0 0 var(--sp-sm); }
.gate-btn {
  width: 100%; padding: 12px; border: none; border-radius: var(--radius-md);
  background: var(--accent-ember); color: #fff; font-size: var(--fs-base); font-weight: 600; cursor: pointer;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 760px) {
  .book-hero { flex-direction: column; }
  .cover { flex: none; width: 120px; height: 164px; }
  .reader-grid { grid-template-columns: 1fr; }
  .toc-panel { position: static; max-height: 240px; order: 2; }
  .chapter-panel { order: 1; padding: var(--sp-lg); }
}
</style>
