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
  padding: 1rem 0;
}

.step-title {
  font-size: 1.4rem;
  color: var(--text-primary, #e0e0ff);
  margin-bottom: 0.5rem;
}

.step-guide {
  color: var(--text-muted, #888);
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.prop-input {
  margin-bottom: 1.5rem;

  :deep(.el-textarea__inner) {
    background: var(--bg-surface, #1a1a3e);
    border-color: var(--border, #2a2a4a);
    color: var(--text-primary, #e0e0ff);
    font-size: 1rem;
    line-height: 1.8;

    &:focus {
      border-color: #409eff;
    }
  }
}

.inspiration {
  .inspiration-label {
    font-size: 0.85rem;
    color: var(--text-muted, #888);
    display: block;
    margin-bottom: 0.5rem;
  }
}

.examples {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.example-tag {
  cursor: pointer;
  white-space: normal;
  height: auto;
  padding: 0.5rem 0.75rem;
  line-height: 1.4;

  &:hover {
    border-color: #409eff;
    color: #409eff;
  }
}
</style>
