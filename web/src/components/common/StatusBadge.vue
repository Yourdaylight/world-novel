<template>
  <span class="status-badge" :class="'status-' + statusClass">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useProgressStore } from '@/stores/progress'
import { formatPhase } from '@/utils/formatters'

const progressStore = useProgressStore()

const statusClass = computed(() => {
  const p = progressStore.phase
  if (p === 'done') return 'done'
  if (p === 'idle' || p === 'error') return 'idle'
  if (progressStore.paused) return 'paused'
  return 'running'
})

const label = computed(() => formatPhase(progressStore.phase))
</script>

<style scoped lang="scss">
.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
}
.status-idle { background: #1e3a5f; color: #60a5fa; }
.status-running { background: #164e63; color: #22d3ee; animation: pulse 2s infinite; }
.status-done { background: #14532d; color: #4ade80; }
.status-paused { background: #713f12; color: #fbbf24; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
