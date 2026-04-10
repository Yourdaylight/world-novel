<template>
  <span class="status-badge" :class="'status-' + statusClass">
    <span v-if="statusClass === 'running'" class="dot"></span>
    {{ label }}
  </span>
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
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 20px;
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 650;
  white-space: nowrap;
  letter-spacing: 0.02em;

  .dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: currentColor;
    animation: dot-pulse 2s ease-in-out infinite;
  }

  &.status-idle     { color: #6b7280; background: rgba(107,114,128,0.08); }
  &.status-running { color: #d97706; background: rgba(217,119,6,0.09); }
  &.status-done    { color: #059669; background: rgba(5,150,105,0.08); }
  &.status-paused  { color: #2563eb; background: rgba(37,99,235,0.08); }
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.35; transform: scale(0.8); }
}
</style>
