<template>
  <div class="home-page">
    <header class="home-header ledger-rule">
      <div class="brand">
        <h1 class="brand-title">WorldEngine</h1>
        <span class="brand-subtitle">造物主的创世工坊</span>
      </div>
      <button class="btn-create" @click="router.push('/create')">
        + 创建新世界
      </button>
    </header>

    <div class="page-title-row ledger-rule">
      <h2 class="page-title">你的世界</h2>
    </div>

    <div class="world-grid" v-loading="novelStore.loading">
      <template v-if="novelStore.novels.length > 0">
        <el-row :gutter="20">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="novel in novelStore.novels" :key="novel.novel_id">
            <WorldCard :novel="novel" @enter="onEnter" @run="onRun" @delete="onDelete" />
          </el-col>
        </el-row>
      </template>
      <div v-else class="empty-home">
        <div class="empty-icon">🌌</div>
        <h2>还没有世界</h2>
        <p>点击上方 "创建新世界" 开始你的造物之旅</p>
        <button class="btn-create" @click="router.push('/create')">
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
    if (res.ok) {
      ElMessage.success('世界已删除')
    }
  } catch {
    // Cancelled
  }
}
</script>

<style scoped lang="scss">
.home-page {
  min-height: 100vh;
  background: var(--bg-void);
  padding: var(--sp-2xl) var(--sp-xl);
  max-width: 1100px;
  margin: 0 auto;
}

.home-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.brand-title {
  font-family: var(--font-ui);
  font-size: var(--fs-3xl);
  font-weight: 300;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.1;
}

.brand-subtitle {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-top: var(--sp-xs);
  display: block;
}

.page-title-row {
  padding-top: var(--sp-lg);
}

.page-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
}

.btn-create {
  background: var(--accent-ember);
  color: var(--text-inverse);
  border: none;
  border-radius: 6px;
  padding: var(--sp-sm) var(--sp-lg);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.02em;

  &:hover {
    background: #db8a52;
  }
}

.world-grid {
  min-height: 400px;
}

.empty-home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--sp-3xl) var(--sp-xl);
  text-align: center;

  .empty-icon {
    font-size: 4rem;
    margin-bottom: var(--sp-lg);
    opacity: 0.6;
  }

  h2 {
    font-family: var(--font-ui);
    font-weight: 400;
    color: var(--text-primary);
    margin-bottom: var(--sp-sm);
  }

  p {
    color: var(--text-muted);
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    margin-bottom: var(--sp-xl);
  }
}
</style>
