<template>
  <div class="ai-feedback">
    <div class="feedback-header">
      <span class="feedback-icon">🤖</span>
      <span class="feedback-title">AI 分析</span>
    </div>

    <div v-if="loading" class="feedback-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="result" class="feedback-content">
      <div class="section" v-if="result.analysis">
        <h4>📊 基调判断</h4>
        <p>{{ result.analysis }}</p>
      </div>

      <div class="section" v-if="result.conflict_points?.length">
        <h4>⚔️ 可挖掘的冲突点</h4>
        <ul>
          <li v-for="(point, i) in result.conflict_points" :key="i">{{ point }}</li>
        </ul>
      </div>

      <div class="section" v-if="result.suggestions?.length">
        <h4>💡 补充建议</h4>
        <ul>
          <li v-for="(suggestion, i) in result.suggestions" :key="i">{{ suggestion }}</li>
        </ul>
      </div>

      <div class="section" v-if="result.references?.length">
        <h4>📚 参考对标</h4>
        <el-tag
          v-for="(ref, i) in result.references"
          :key="i"
          size="small"
          class="ref-tag"
          effect="plain"
        >
          {{ ref }}
        </el-tag>
      </div>
    </div>

    <div v-else class="feedback-empty">
      <p>输入内容后，AI 将实时分析你的构想</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { analyzeProposition } from '@/api/novels'
import type { AiAnalysisResult, Propositions } from '@/api/types'

const props = defineProps<{
  step: number
  text: string
  context: Partial<Propositions>
}>()

const loading = ref(false)
const result = ref<AiAnalysisResult | null>(null)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.text,
  (newText) => {
    if (debounceTimer) clearTimeout(debounceTimer)
    if (!newText || newText.trim().length < 10) {
      result.value = null
      return
    }
    debounceTimer = setTimeout(() => {
      fetchAnalysis(newText)
    }, 800)
  }
)

async function fetchAnalysis(text: string) {
  loading.value = true
  try {
    result.value = await analyzeProposition(props.step, text, props.context)
  } catch {
    result.value = null
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.ai-feedback {
  background: var(--bg-surface, #1a1a3e);
  border: 1px solid var(--border, #2a2a4a);
  border-radius: 12px;
  padding: 1.25rem;
  min-height: 300px;
}

.feedback-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border, #2a2a4a);

  .feedback-icon {
    font-size: 1.2rem;
  }
  .feedback-title {
    font-weight: 600;
    color: var(--text-primary, #e0e0ff);
  }
}

.feedback-loading {
  padding: 1rem 0;
}

.feedback-content {
  .section {
    margin-bottom: 1rem;

    h4 {
      font-size: 0.85rem;
      color: var(--text-secondary, #aaa);
      margin-bottom: 0.4rem;
    }

    p {
      color: var(--text-primary, #e0e0ff);
      line-height: 1.6;
      font-size: 0.9rem;
    }

    ul {
      list-style: none;
      padding: 0;
      margin: 0;

      li {
        color: var(--text-primary, #e0e0ff);
        font-size: 0.85rem;
        line-height: 1.6;
        padding-left: 1rem;
        position: relative;

        &::before {
          content: '•';
          position: absolute;
          left: 0;
          color: #409eff;
        }
      }
    }
  }
}

.ref-tag {
  margin-right: 0.5rem;
  margin-bottom: 0.25rem;
}

.feedback-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;

  p {
    color: var(--text-muted, #888);
    font-size: 0.9rem;
  }
}
</style>
