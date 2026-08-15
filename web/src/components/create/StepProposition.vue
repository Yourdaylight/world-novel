<template>
  <div class="step-proposition">
    <h2 class="step-title">{{ title }}</h2>
    <p class="step-guide">{{ guide }}</p>

    <el-input
      type="textarea"
      :rows="6"
      :model-value="modelValue"
      @update:model-value="$emit('update:modelValue', $event)"
      placeholder="在这里描述你的构想..."
      class="prop-input"
    />

    <div class="inspiration">
      <span class="inspiration-label">💡 灵感提示：</span>
      <div class="examples">
        <el-tag
          v-for="(example, i) in examples"
          :key="i"
          class="example-tag"
          @click="$emit('update:modelValue', example)"
          effect="plain"
          type="info"
        >
          {{ example.length > 40 ? example.slice(0, 40) + '...' : example }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  step: number
  title: string
  guide: string
  examples: string[]
  modelValue: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<style scoped lang="scss">
.step-proposition {
  background: var(--bg-surface);
}

.step-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  color: var(--text-primary);
  margin-bottom: var(--sp-sm);
  letter-spacing: -0.02em;
}

.step-guide {
  color: var(--text-secondary);
  margin-bottom: var(--sp-lg);
  line-height: 1.6;
}

.prop-input {
  margin-bottom: var(--sp-lg);

  :deep(.el-textarea__inner) {
    background: var(--bg-void);
    border-color: var(--border-default);
    color: var(--text-primary);
    font-size: var(--fs-base);
    line-height: 1.8;
    border-radius: var(--radius-md);
    padding: var(--sp-md);

    &:focus {
      border-color: var(--accent-ember);
      box-shadow: 0 0 0 3px var(--accent-ember-dim);
    }
  }
}

.inspiration {
  .inspiration-label {
    font-size: var(--fs-sm);
    color: var(--text-muted);
    display: block;
    margin-bottom: var(--sp-sm);
  }
}

.examples {
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}

.example-tag {
  cursor: pointer;
  white-space: normal;
  height: auto;
  padding: var(--sp-sm) var(--sp-md);
  line-height: 1.4;
  background: var(--bg-elevated);
  border-color: var(--border-default);
  color: var(--text-secondary);

  &:hover {
    border-color: var(--accent-ember);
    color: var(--accent-ember);
  }
}
</style>
