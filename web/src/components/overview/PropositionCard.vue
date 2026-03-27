<template>
  <div class="proposition-item" :class="`accent-${color}`">
    <div class="prop-header">
      <span class="prop-icon">{{ icon }}</span>
      <span class="prop-label">{{ label }}</span>
    </div>
    <p class="prop-text">{{ text || '暂无设定' }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  label: string
  text: string
  color: 'blue' | 'green' | 'red'
}>()
</script>

<style scoped lang="scss">
.proposition-item {
  border: 1px solid var(--border-rule);
  border-radius: 6px;
  padding: var(--sp-md);
  border-left: 3px solid transparent;

  &.accent-blue {
    border-left-color: var(--accent-aurora);
  }
  &.accent-green {
    border-left-color: var(--accent-jade);
  }
  &.accent-red {
    border-left-color: var(--accent-cinnabar);
  }
}

.prop-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-sm);

  .prop-icon {
    font-size: 1.1rem;
  }
  .prop-label {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
  }
}

.prop-text {
  font-family: var(--font-ui);
  color: var(--text-primary);
  line-height: 1.85;
  font-size: var(--fs-base);
  margin: 0;
}
</style>
