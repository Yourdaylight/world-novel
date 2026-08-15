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
.checkpoint-list {
  display: flex;
  flex-direction: column;
}

.cp-item {
  padding: var(--sp-md) 0;
  border-bottom: 1px solid var(--border-muted);
}

.cp-item:last-child {
  border-bottom: none;
}

.cp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-xs);
}

.cp-title {
  font-weight: 600;
  color: var(--text-primary);
}

.cp-meta {
  display: flex;
  gap: var(--sp-lg);
  font-size: var(--fs-sm);
  color: var(--text-muted);
}
</style>
