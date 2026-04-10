<template>
  <div class="home-page">
    <!-- Hero Header -->
    <header class="home-header">
      <div class="brand">
        <div class="brand-icon">
          <svg width="28" height="28" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="45" stroke="currentColor" stroke-width="2.5" opacity="0.2"/>
            <path d="M30 50 Q 35 25, 50 20 Q 65 25, 70 50 Q 65 75, 50 80 Q 35 75, 30 50Z" stroke="currentColor" stroke-width="2" opacity="0.5"/>
            <circle cx="50" cy="48" r="8" fill="currentColor" opacity="0.7"/>
            <line x1="50" y1="40" x2="50" y2="18" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
            <line x1="58" y1="52" x2="78" y2="60" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
          </svg>
        </div>
        <div>
          <h1 class="brand-title">WorldNovel</h1>
          <p class="brand-subtitle">造物主的创世工坊</p>
        </div>
      </div>
      <button class="btn-create" @click="router.push('/create')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        创建新世界
      </button>
    </header>

    <div class="page-title-row ledger-rule">
      <h2 class="page-title">你的世界</h2>
      <span class="page-count" v-if="novelStore.novels.length">{{ novelStore.novels.length }} 个世界</span>
    </div>

    <div class="world-grid" v-loading="novelStore.loading">
      <template v-if="novelStore.novels.length > 0">
        <div class="world-list">
          <WorldCard
            v-for="(novel, idx) in novelStore.novels"
            :key="novel.novel_id"
            :novel="novel"
            :style="{ animationDelay: `${idx * 80}ms` }"
            @enter="onEnter"
            @run="onRun"
            @delete="onDelete"
          />
        </div>
      </template>

      <div v-else class="empty-home animate-fade-up">
        <div class="empty-visual">
          <div class="empty-orb"></div>
          <div class="empty-ring empty-ring-1"></div>
          <div class="empty-ring empty-ring-2"></div>
        </div>
        <h2 class="empty-title">还没有世界</h2>
        <p class="empty-desc">点击上方按钮，开始创造属于你的第一个世界</p>
        <button class="btn-create btn-create-lg" @click="router.push('/create')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          开始创世
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useNovelStore } from '@/stores/novel'
import { startGeneration } from '@/api/novels'
import WorldCard from './WorldCard.vue'
import type { NovelInfo } from '@/api/types'

const router = useRouter()
const novelStore = useNovelStore()

onMounted(() => {
  novelStore.loadNovels()
})

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
</script>

<style scoped lang="scss">
.home-page {
  min-height: 100vh;
  background: var(--bg-gradient);
  padding: var(--sp-3xl) var(--sp-xl);
  max-width: 1100px;
  margin: 0 auto;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: var(--bg-noise);
    pointer-events: none;
    z-index: 0;
  }

  > * { position: relative; z-index: 1; }
}

/* === Hero Header === */
.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--sp-xl);
  border-bottom: 1px solid var(--border-default);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
}

.brand-icon {
  color: var(--accent-ember);
  opacity: 0.85;
  animation: icon-float 6s ease-in-out infinite;
}

.brand-title {
  font-family: var(--font-display);
  font-size: var(--fs-3xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.15;
  letter-spacing: -0.03em;
}

.brand-subtitle {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-top: 4px;
  display: block;
}

/* === Create Button — premium feel === */
.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 10px 22px;
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.02em;
  transition: all var(--duration-base) ease;
  box-shadow: 0 2px 10px rgba(217, 119, 6, 0.3);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(217, 119, 6, 0.38);
    background: linear-gradient(135deg, #b45309, #92400e);
  }
}

.btn-create-lg {
  padding: 13px 32px;
  font-size: var(--fs-base);
  border-radius: var(--radius-lg);
}

/* === Page Title Row === */
.page-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-top: var(--sp-xl);
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.page-count {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

/* === Grid / List === */
.world-grid {
  min-height: 420px;
  margin-top: var(--sp-lg);
}

.world-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--sp-md);
}

/* === Empty State — cosmic vibe === */
.empty-home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--sp-3xl) var(--sp-xl);
  text-align: center;
}

.empty-visual {
  position: relative;
  width: 140px;
  height: 140px;
  margin-bottom: var(--sp-xl);
}

.empty-orb {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, rgba(217,119,6,0.25), rgba(217,119,6,0.06));
  box-shadow: 0 0 40px rgba(217,119,6,0.08), inset 0 0 12px rgba(255,255,255,0.05);
  animation: orb-pulse 4s ease-in-out infinite;
}

.empty-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  border: 1px solid var(--border-default);

  &.empty-ring-1 {
    width: 96px;
    height: 96px;
    transform: translate(-50%, -50%) rotate(0deg);
    animation: ring-spin 20s linear infinite;
    border-style: dashed;
    opacity: 0.45;
  }

  &.empty-ring-2 {
    width: 130px;
    height: 130px;
    transform: translate(-50%, -50%) rotate(120deg);
    animation: ring-spin 28s linear infinite reverse;
    border-style: dotted;
    opacity: 0.25;
  }
}

.empty-title {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: var(--fs-lg);
  color: var(--text-primary);
  margin-bottom: var(--sp-sm);
  letter-spacing: -0.01em;
}

.empty-desc {
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  margin-bottom: var(--sp-xl);
  max-width: 320px;
  line-height: 1.6;
}

@keyframes icon-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-4px); }
}
@keyframes orb-pulse {
  0%, 100% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
  50%      { opacity: 0.7; transform: translate(-50%, -50%) scale(0.92); }
}
@keyframes ring-spin {
  to { transform: translate(-50%, -50%) rotate(360deg); }
}
</style>
