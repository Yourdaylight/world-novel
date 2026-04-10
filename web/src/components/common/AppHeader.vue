<template>
  <header class="app-header">
    <div class="header-left">
      <el-button v-if="showBack" text class="back-btn" @click="router.push('/')">
        ← 首页
      </el-button>
      <h1>🌍 WorldNovel</h1>
    </div>
    <div class="header-right">
      <NovelSelector />
      <ProgressBar />
      <StatusBadge />
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import NovelSelector from './NovelSelector.vue'
import ProgressBar from './ProgressBar.vue'
import StatusBadge from './StatusBadge.vue'

defineProps<{
  showBack?: boolean
}>()

const router = useRouter()
</script>

<style scoped lang="scss">
.app-header {
  background: linear-gradient(135deg, var(--bg-surface) 0%, var(--bg-elevated) 100%);
  padding: 1rem 2rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;

  h1 {
    font-size: 1.4rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.back-btn {
  font-size: 0.9rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}
</style>
