<template>
  <div class="landing-page">
    <!-- Navigation -->
    <nav class="landing-nav" :class="{ 'is-scrolled': isScrolled }">
      <div class="nav-inner">
        <div class="nav-brand" @click="scrollTo('top')">
          <span class="brand-logo">&#10022;</span>
          <span class="brand-name">WorldNovel</span>
        </div>

        <div class="nav-links">
          <a class="nav-link" @click.prevent="scrollTo('features')">功能</a>
          <a class="nav-link" @click.prevent="scrollTo('worlds')">世界</a>
          <a class="nav-link" @click="router.push('/create')">创建世界</a>
        </div>

        <div class="nav-actions">
          <template v-if="authStore.isAuthEnabled">
            <template v-if="authStore.isAuthenticated">
              <div class="user-menu" @click="router.push('/profile')">
                <div v-if="authStore.identity?.avatar" class="user-avatar">
                  <img :src="authStore.identity.avatar" alt="">
                </div>
                <div v-else class="user-avatar user-avatar--placeholder">
                  {{ displayInitial }}
                </div>
                <span class="user-name">{{ authStore.displayName }}</span>
              </div>
            </template>
            <button v-else class="btn-login" @click="authStore.login()">登录</button>
          </template>
          <button class="btn-primary" @click="router.push('/create')">
            开始创作
          </button>
        </div>
      </div>
    </nav>

    <!-- Hero -->
    <section class="hero" ref="heroRef">
      <div class="hero-inner">
        <div class="hero-badge">
          <span class="badge-dot"></span>
          AI 驱动的长篇小说生成器
        </div>
        <h1 class="hero-title">
          从零开始，创造你的<br>
          <span class="text-gradient">完整小说世界</span>
        </h1>
        <p class="hero-subtitle">
          WorldNovel 帮助你构建世界观、设计角色、铺设大纲，并自动生成章节内容。
          无需从零码字，让 AI 成为你的共创伙伴。
        </p>
        <div class="hero-actions">
          <button class="btn-hero-primary" @click="router.push('/create')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            免费创建第一个世界
          </button>
          <button class="btn-hero-secondary" @click="scrollTo('features')">
            了解如何工作
          </button>
        </div>

        <div class="hero-stats" v-if="stats.totalWorlds > 0">
          <div class="stat-item">
            <span class="stat-value">{{ stats.totalWorlds }}</span>
            <span class="stat-label">已创建世界</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ stats.totalChapters }}</span>
            <span class="stat-label">生成章节</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ formatNumber(stats.totalWords) }}</span>
            <span class="stat-label">累计字数</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section id="features" class="features">
      <div class="section-inner">
        <div class="section-header">
          <span class="section-tag">核心功能</span>
          <h2 class="section-title">一部小说，从构想到成稿</h2>
          <p class="section-desc">
            WorldNovel 不是简单的文本生成器，而是一套完整的小说创作工作流。
          </p>
        </div>

        <div class="feature-grid">
          <div class="feature-card">
            <div class="feature-icon feature-icon--orange">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            </div>
            <h3>世界观构建</h3>
            <p>定义世界的力量体系、势力分布、历史事件与地理环境，AI 帮你补全细节。</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon feature-icon--blue">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <h3>角色设计</h3>
            <p>创建角色档案、关系网、情感曲线与记忆系统，让角色行为贯穿全书。</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon feature-icon--green">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </div>
            <h3>大纲与时间线</h3>
            <p>用时间轴组织剧情，设置伏笔与回收点，确保故事结构完整。</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon feature-icon--purple">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            </div>
            <h3>自动章节生成</h3>
            <p>一键启动生成流水线，AI 根据大纲自动撰写章节，你只需审核与调整。</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon feature-icon--pink">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
            </div>
            <h3>史官对话</h3>
            <p>随时与 AI 史官对话，询问设定、梳理剧情、获取创作建议。</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon feature-icon--cyan">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            </div>
            <h3>进度监控</h3>
            <p>实时查看生成进度、Token 消耗与章节统计，创作过程一目了然。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Worlds / Quick Start -->
    <section id="worlds" class="worlds-section">
      <div class="section-inner">
        <div class="section-header">
          <span class="section-tag">你的世界</span>
          <h2 class="section-title">继续创作或开启新篇</h2>
        </div>

        <div v-if="authStore.isAuthEnabled && !authStore.isAuthenticated" class="auth-prompt">
          <p>登录后即可查看和管理你的世界</p>
          <button class="btn-primary" @click="authStore.login()">立即登录</button>
        </div>

        <div v-else v-loading="novelStore.loading" class="worlds-grid">
          <template v-if="novelStore.novels.length > 0">
            <WorldCard
              v-for="(novel, idx) in novelStore.novels"
              :key="novel.novel_id"
              :novel="novel"
              :style="{ animationDelay: `${idx * 60}ms` }"
              @enter="onEnter"
              @run="onRun"
              @delete="onDelete"
            />
          </template>

          <div v-else class="create-prompt-card" @click="router.push('/create')">
            <div class="create-prompt-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </div>
            <h3>创建第一个世界</h3>
            <p>还没有世界？点击这里，3 步开启你的小说创作之旅。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- How it works -->
    <section class="how-it-works">
      <div class="section-inner">
        <div class="section-header">
          <span class="section-tag">快速开始</span>
          <h2 class="section-title">三步开始创作</h2>
        </div>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <h3>创建世界</h3>
            <p>填写小说标题、类型与核心三命题，确立故事基调。</p>
          </div>
          <div class="step-arrow">&rarr;</div>
          <div class="step">
            <div class="step-num">2</div>
            <h3>完善设定</h3>
            <p>补充世界观、角色、大纲与伏笔，构建故事骨架。</p>
          </div>
          <div class="step-arrow">&rarr;</div>
          <div class="step">
            <div class="step-num">3</div>
            <h3>一键生成</h3>
            <p>启动生成流水线，AI 自动撰写章节并持续追踪进度。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta-section">
      <div class="cta-inner">
        <h2>准备好创造你的世界了吗？</h2>
        <p>加入 WorldNovel，让 AI 成为你长篇创作的得力助手。</p>
        <button class="btn-cta" @click="router.push('/create')">
          立即免费创建
        </button>
      </div>
    </section>

    <!-- Footer -->
    <footer class="landing-footer">
      <div class="footer-inner">
        <div class="footer-brand">
          <span class="brand-logo">&#10022;</span>
          <span>WorldNovel</span>
        </div>
        <p class="footer-copy">造物主的创世工坊</p>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import { startGeneration } from '@/api/novels'
import WorldCard from './WorldCard.vue'
import type { NovelInfo } from '@/api/types'

const router = useRouter()
const novelStore = useNovelStore()
const authStore = useAuthStore()

const isScrolled = ref(false)
const heroRef = ref<HTMLElement | null>(null)

const displayInitial = computed(() => {
  const name = authStore.identity?.display_name || authStore.identity?.username || '用户'
  return name.slice(0, 1).toUpperCase()
})

const stats = computed(() => {
  const novels = novelStore.novels
  return {
    totalWorlds: novels.length,
    totalChapters: novels.reduce((sum, n) => sum + (n.chapters_completed || 0), 0),
    totalWords: novels.reduce((sum, n) => sum + (n.word_count || 0), 0),
  }
})

function formatNumber(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toLocaleString()
}

function onScroll() {
  isScrolled.value = window.scrollY > 10
}

function scrollTo(id: string) {
  if (id === 'top') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  const el = document.getElementById(id)
  if (el) {
    const navHeight = 64
    const top = el.getBoundingClientRect().top + window.scrollY - navHeight
    window.scrollTo({ top, behavior: 'smooth' })
  }
}

function onEnter(novel: NovelInfo) {
  novelStore.switchNovel(novel.novel_id)
  router.push(`/world/${novel.novel_id}/overview`)
}

async function onRun(novel: NovelInfo) {
  await novelStore.switchNovel(novel.novel_id)
  const res = await startGeneration(novel.novel_id)
  if (res.ok) {
    ElMessage.success('生成已启动，跳转到控制台...')
    router.push(`/world/${novel.novel_id}/control`)
  } else {
    ElMessage.error(res.error || '启动失败')
  }
}

async function onDelete(novel: NovelInfo) {
  try {
    await ElMessageBox.confirm(
      `确定要删除世界 "${novel.title}" 吗？所有数据将被清除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const res = await novelStore.removeWorld(novel.novel_id)
    if (res.ok) ElMessage.success('世界已删除')
  } catch {
    // Cancelled
  }
}

onMounted(() => {
  authStore.init().then(() => {
    novelStore.loadNovels()
  })
  window.addEventListener('scroll', onScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<style scoped lang="scss">
.landing-page {
  min-height: 100vh;
  background: var(--bg-void);
  color: var(--text-primary);
}

/* === Navigation === */
.landing-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: transparent;
  transition: background var(--duration-base) ease, box-shadow var(--duration-base) ease;

  &.is-scrolled {
    background: var(--bg-glass);
    backdrop-filter: blur(12px);
    box-shadow: var(--shadow-sm);
    border-bottom: 1px solid var(--border-default);
  }
}

.nav-inner {
  max-width: 1280px;
  margin: 0 auto;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-lg);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  cursor: pointer;

  .brand-logo {
    font-size: 24px;
    color: var(--accent-ember);
  }

  .brand-name {
    font-family: var(--font-display);
    font-size: var(--fs-lg);
    font-weight: 600;
    letter-spacing: -0.02em;
  }
}

.nav-links {
  display: flex;
  align-items: center;
  gap: var(--sp-xl);

  .nav-link {
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    text-decoration: none;
    cursor: pointer;
    transition: color var(--duration-fast) ease;

    &:hover {
      color: var(--text-primary);
    }
  }
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
}

.user-menu {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  cursor: pointer;
  padding: 4px 12px 4px 4px;
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) ease;

  &:hover {
    background: var(--bg-elevated);
  }
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--accent-ember-dim);
  display: flex;
  align-items: center;
  justify-content: center;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  &--placeholder {
    color: var(--accent-ember);
    font-size: var(--fs-sm);
    font-weight: 600;
  }
}

.user-name {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-login {
  background: transparent;
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  padding: 8px 18px;
  font-size: var(--fs-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast) ease;

  &:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
    background: var(--bg-elevated);
  }
}

.btn-primary {
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 8px 18px;
  font-size: var(--fs-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-fast) ease;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(217, 119, 6, 0.35);
  }
}

/* === Hero === */
.hero {
  padding: 140px var(--sp-lg) 80px;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(217, 119, 6, 0.12) 0%, transparent 55%),
    var(--bg-gradient);
  text-align: center;
}

.hero-inner {
  max-width: 900px;
  margin: 0 auto;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: 6px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 100px;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin-bottom: var(--sp-xl);

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-ember);
    animation: pulse 2s ease-in-out infinite;
  }
}

.hero-title {
  font-family: var(--font-display);
  font-size: clamp(40px, 6vw, 64px);
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin-bottom: var(--sp-lg);

  .text-gradient {
    background: linear-gradient(135deg, #d97706, #b45309);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.hero-subtitle {
  font-size: var(--fs-md);
  color: var(--text-secondary);
  line-height: 1.7;
  max-width: 640px;
  margin: 0 auto var(--sp-xl);
}

.hero-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-md);
  margin-bottom: var(--sp-2xl);
}

.btn-hero-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-sm);
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
  border-radius: var(--radius-lg);
  padding: 14px 28px;
  font-size: var(--fs-base);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  box-shadow: 0 4px 16px rgba(217, 119, 6, 0.35);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(217, 119, 6, 0.45);
  }
}

.btn-hero-secondary {
  background: var(--bg-surface);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 14px 28px;
  font-size: var(--fs-base);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-fast) ease;

  &:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }
}

.hero-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2xl);
  padding-top: var(--sp-xl);
  border-top: 1px solid var(--border-default);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;

  .stat-value {
    font-family: var(--font-data);
    font-size: var(--fs-xl);
    font-weight: 600;
    color: var(--text-primary);
  }

  .stat-label {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
}

/* === Sections === */
.section-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 80px var(--sp-lg);
}

.section-header {
  text-align: center;
  margin-bottom: var(--sp-2xl);
}

.section-tag {
  display: inline-block;
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--accent-ember);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: var(--sp-sm);
}

.section-title {
  font-family: var(--font-display);
  font-size: var(--fs-2xl);
  font-weight: 400;
  letter-spacing: -0.02em;
  margin-bottom: var(--sp-sm);
}

.section-desc {
  font-size: var(--fs-base);
  color: var(--text-secondary);
  max-width: 560px;
  margin: 0 auto;
  line-height: 1.7;
}

/* === Features === */
.features {
  background: var(--bg-surface);
  border-top: 1px solid var(--border-default);
  border-bottom: 1px solid var(--border-default);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--sp-lg);
}

.feature-card {
  padding: var(--sp-lg);
  background: var(--bg-void);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  transition: all var(--duration-fast) ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
    border-color: var(--border-active);
  }

  h3 {
    font-family: var(--font-display);
    font-size: var(--fs-lg);
    font-weight: 400;
    margin: var(--sp-md) 0 var(--sp-xs);
  }

  p {
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    line-height: 1.6;
  }
}

.feature-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;

  &--orange { background: rgba(217, 119, 6, 0.12); color: #d97706; }
  &--blue { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
  &--green { background: rgba(5, 150, 105, 0.12); color: #059669; }
  &--purple { background: rgba(124, 58, 237, 0.12); color: #7c3aed; }
  &--pink { background: rgba(219, 39, 119, 0.12); color: #db2777; }
  &--cyan { background: rgba(8, 145, 178, 0.12); color: #0891b2; }
}

/* === Worlds === */
.worlds-section {
  background: var(--bg-void);
}

.auth-prompt {
  text-align: center;
  padding: var(--sp-3xl) var(--sp-lg);
  background: var(--bg-surface);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-lg);

  p {
    color: var(--text-secondary);
    margin-bottom: var(--sp-md);
  }
}

.worlds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--sp-lg);
}

.create-prompt-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--sp-2xl);
  background: var(--bg-surface);
  border: 2px dashed var(--border-default);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  min-height: 240px;

  &:hover {
    border-color: var(--accent-ember);
    background: var(--bg-elevated);
  }

  .create-prompt-icon {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--accent-ember-dim);
    color: var(--accent-ember);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: var(--sp-md);
  }

  h3 {
    font-family: var(--font-display);
    font-size: var(--fs-lg);
    font-weight: 400;
    margin-bottom: var(--sp-xs);
  }

  p {
    font-size: var(--fs-sm);
    color: var(--text-muted);
    max-width: 280px;
  }
}

/* === How it works === */
.how-it-works {
  background: var(--bg-surface);
  border-top: 1px solid var(--border-default);
}

.steps {
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: var(--sp-lg);
}

.step {
  flex: 1;
  max-width: 300px;
  text-align: center;
  padding: var(--sp-lg);
  background: var(--bg-void);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);

  .step-num {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, #d97706, #b45309);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    margin: 0 auto var(--sp-md);
  }

  h3 {
    font-family: var(--font-display);
    font-size: var(--fs-lg);
    font-weight: 400;
    margin-bottom: var(--sp-xs);
  }

  p {
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    line-height: 1.6;
  }
}

.step-arrow {
  display: flex;
  align-items: center;
  font-size: 28px;
  color: var(--accent-ember);
}

/* === CTA === */
.cta-section {
  padding: 80px var(--sp-lg);
  background:
    radial-gradient(ellipse at 50% 100%, rgba(217, 119, 6, 0.12) 0%, transparent 55%),
    var(--bg-gradient);
}

.cta-inner {
  max-width: 640px;
  margin: 0 auto;
  text-align: center;

  h2 {
    font-family: var(--font-display);
    font-size: var(--fs-2xl);
    font-weight: 400;
    margin-bottom: var(--sp-sm);
  }

  p {
    color: var(--text-secondary);
    margin-bottom: var(--sp-xl);
  }
}

.btn-cta {
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
  border-radius: var(--radius-lg);
  padding: 16px 36px;
  font-size: var(--fs-md);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  box-shadow: 0 4px 20px rgba(217, 119, 6, 0.35);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(217, 119, 6, 0.45);
  }
}

/* === Footer === */
.landing-footer {
  background: var(--bg-surface);
  border-top: 1px solid var(--border-default);
  padding: var(--sp-xl) var(--sp-lg);
}

.footer-inner {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  font-family: var(--font-display);
  font-size: var(--fs-md);

  .brand-logo {
    color: var(--accent-ember);
  }
}

.footer-copy {
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

/* === Animations === */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* === Responsive === */
@media (max-width: 768px) {
  .nav-links {
    display: none;
  }

  .hero {
    padding: 120px var(--sp-md) 60px;
  }

  .hero-actions {
    flex-direction: column;
    width: 100%;

    button {
      width: 100%;
      justify-content: center;
    }
  }

  .hero-stats {
    flex-direction: column;
    gap: var(--sp-md);
  }

  .section-inner {
    padding: 60px var(--sp-md);
  }

  .feature-grid,
  .worlds-grid {
    grid-template-columns: 1fr;
  }

  .steps {
    flex-direction: column;
    align-items: center;
  }

  .step-arrow {
    transform: rotate(90deg);
  }

  .footer-inner {
    flex-direction: column;
    gap: var(--sp-sm);
    text-align: center;
  }
}
</style>
