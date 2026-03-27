<template>
  <div class="step-params">
    <h2>设定基础参数</h2>
    <p class="guide-text">为你的世界配置生成参数</p>

    <el-form label-position="top" class="params-form">
      <el-form-item label="小说标题" required>
        <el-input
          :model-value="title"
          @update:model-value="$emit('update:title', $event)"
          placeholder="给你的世界起个名字"
          size="large"
        />
      </el-form-item>

      <el-form-item label="类型">
        <el-select
          :model-value="genre"
          @update:model-value="$emit('update:genre', $event)"
          size="large"
          style="width: 100%"
        >
          <el-option v-for="g in genres" :key="g" :label="g" :value="g" />
        </el-select>
      </el-form-item>

      <el-form-item label="初始章节数（后续可继续生成更多章节）">
        <div class="input-with-hint">
          <el-input-number
            :model-value="numChapters"
            @update:model-value="(v: any) => $emit('update:numChapters', Number(v) || 5)"
            :min="1"
            :max="9999"
            :step="1"
            size="large"
            style="width: 200px"
          />
          <span class="form-hint">章节按逐章方式生成，可随时暂停和继续</span>
        </div>
      </el-form-item>

      <el-form-item label="主要角色数">
        <el-slider
          :model-value="numCharacters"
          @update:model-value="(v: any) => $emit('update:numCharacters', Number(v))"
          :min="3"
          :max="20"
          :step="1"
          show-input
        />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  genre: string
  numChapters: number
  numCharacters: number
  loading: boolean
}>()

defineEmits<{
  'update:title': [value: string]
  'update:genre': [value: string]
  'update:numChapters': [value: number]
  'update:numCharacters': [value: number]
}>()

const genres = ['玄幻', '武侠', '科幻', '言情', '悬疑', '历史', '末日', '都市', '奇幻', '军事']
</script>

<style scoped lang="scss">
.step-params {
  max-width: 600px;
  margin: 0 auto;
  padding: 1rem 0;

  h2 {
    font-size: 1.4rem;
    color: var(--text-primary, #e0e0ff);
    margin-bottom: 0.5rem;
  }

  .guide-text {
    color: var(--text-muted, #888);
    margin-bottom: 2rem;
  }
}

.params-form {
  :deep(.el-form-item__label) {
    color: var(--text-secondary, #aaa);
    font-weight: 500;
  }
  .input-with-hint {
    display: flex;
    flex-direction: column;
  }
  .form-hint {
    display: block;
    font-size: 0.78rem;
    color: var(--text-muted, #888);
    margin-top: 0.4rem;
  }
}
</style>
