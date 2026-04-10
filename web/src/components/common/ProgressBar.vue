<template>
  <div class="progress-bar-container" v-if="progressStore.total > 0">
    <div class="progress-bar">
      <div
        class="progress-bar-fill"
        :style="{ width: progressStore.percent + '%' }"
      ></div>
    </div>
    <span class="progress-text font-data">{{ progressStore.completed }}/{{ progressStore.total }} 章</span>
  </div>
</template>

<script setup lang="ts">
import { useProgressStore } from '@/stores/progress'

const progressStore = useProgressStore()
</script>

<style scoped lang="scss">
.progress-bar-container {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
}

.progress-bar {
  width: 200px;
  height: 5px;
  background: var(--bg-elevated);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #d97706, #f59e0b);
  border-radius: 3px;
  transition: width 0.6s var(--ease-out-expo);
}

.progress-text {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  white-space: nowrap;
}
</style>