<template>
  <div class="checkpoint-list" v-loading="loading">
    <template v-if="progressStore.checkpoints.length">
      <div v-for="cp in progressStore.checkpoints" :key="cp.checkpoint_id" class="cp-item">
        <div class="cp-header">
          <span class="cp-title">{{ cp.novel_title || '未命名' }}</span>
          <el-tag size="small" :type="cp.phase === 'done' ? 'success' : 'info'">{{ cp.phase }}</el-tag>
        </div>
        <div class="cp-meta">
          <span>📅 {{ formatDate(cp.created_at) }}</span>
          <span>📝 {{ cp.completed_chapters }}/{{ cp.total_chapters }} 章</span>
        </div>
      </div>
    </template>
    <EmptyState v-else-if="!loading" message="暂无检查点" icon="💾" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useProgressStore } from '@/stores/progress'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatDate } from '@/utils/formatters'

const progressStore = useProgressStore()
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  await progressStore.loadCheckpoints()
  loading.value = false
})
</script>

<style scoped lang="scss">
.cp-item {
  padding: 0.75rem;
  background: var(--bg-elevated);
  border-radius: 6px;
  margin-bottom: 0.5rem;
}
.cp-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;
}
.cp-title { font-weight: 600; }
.cp-meta {
  display: flex; gap: 1.5rem; font-size: 0.8rem; color: var(--text-muted);
}
</style>
