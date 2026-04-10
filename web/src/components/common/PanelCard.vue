<template>
  <div class="panel-section">
    <div class="panel-section-header" v-if="title">
      <span class="panel-section-icon" v-if="icon">{{ icon }}</span>
      <span class="panel-section-title">{{ title }}</span>
      <slot name="header-extra" />
    </div>
    <div class="panel-section-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  icon?: string
}>()
</script>

<style scoped lang="scss">
.panel-section {
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--border-default);
  padding-bottom: var(--sp-lg);
  margin-bottom: var(--sp-lg);

  &:last-child {
    border-bottom: none;
    margin-bottom: 0;
  }
}

.panel-section-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding-bottom: var(--sp-md);
  margin-bottom: var(--p-md, var(--sp-md));
  border-bottom: 1px solid var(--border-muted);
}

.panel-section-icon {
  font-size: 1.1rem;
  opacity: 0.7;
}

.panel-section-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.panel-section-body {
  // No extra padding — ledger style
}
</style>