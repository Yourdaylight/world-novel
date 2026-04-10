<template>
  <div class="empty-state">
    <div class="empty-visual">
      <div class="empty-orb"></div>
    </div>
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
}

.empty-visual {
  position: relative;
  width: 64px;
  height: 64px;
  margin-bottom: var(--sp-md);
}

.empty-orb {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, rgba(217,119,6,0.18), rgba(217,119,6,0.04));
  box-shadow: 0 0 24px rgba(217,119,6,0.06);
  animation: orb-pulse 4s ease-in-out infinite;

  &::after {
    content: '';
    position: absolute;
    top: -10px; left: -10px;
    right: -10px; bottom: -10px;
    border-radius: 50%;
    border: 1px dashed var(--border-default);
    animation: ring-spin 16s linear infinite reverse;
    opacity: 0.3;
  }
}

.empty-text {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
  text-align: center;
}

@keyframes orb-pulse {
  0%, 100% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
  50%      { opacity: 0.55; transform: translate(-50%, -50%) scale(0.88); }
}
@keyframes ring-spin { to { transform: rotate(360deg); } }
</style>
