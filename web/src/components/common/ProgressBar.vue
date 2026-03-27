<template>
  <div class="progress-bar-container" v-if="progressStore.total > 0">
    <div class="progress-bar">
      <div class="progress-bar-fill" :style="{ width: progressStore.percent + '%' }"></div>
    </div>
    <span class="progress-text">{{ progressStore.completed }}/{{ progressStore.total }} 章</span>
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
  gap: 0.75rem;
}

.progress-bar {
  width: 200px;
  height: 8px;
  background: var(--bg-elevated);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-text {
  font-size: 0.85rem;
  color: var(--text-muted);
  white-space: nowrap;
}
</style>
