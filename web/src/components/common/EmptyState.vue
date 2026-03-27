<template>
  <div class="empty-state">
    <div class="empty-icon">{{ icon || '📭' }}</div>
    <p class="empty-text">{{ message || '暂无数据' }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon?: string
  message?: string
}>()
</script>

<style scoped lang="scss">
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--sp-2xl) var(--sp-md);
  color: var(--text-muted);
}
.empty-icon {
  font-size: 2.5rem;
  margin-bottom: var(--sp-md);
  opacity: 0.6;
}
.empty-text {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
}
</style>
