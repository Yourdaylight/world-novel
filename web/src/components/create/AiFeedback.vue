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
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--sp-lg);
  min-height: 300px;
}

.feedback-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-md);
  padding-bottom: var(--sp-sm);
  border-bottom: 1px solid var(--border-default);

  .feedback-icon {
    font-size: var(--fs-md);
  }
  .feedback-title {
    font-weight: 600;
    color: var(--text-primary);
  }
}

.feedback-loading {
  padding: var(--sp-md) 0;
}

.feedback-content {
  .section {
    margin-bottom: var(--sp-md);

    h4 {
      font-size: var(--fs-xs);
      color: var(--text-secondary);
      margin-bottom: var(--sp-xs);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    p {
      color: var(--text-primary);
      line-height: 1.6;
      font-size: var(--fs-sm);
    }

    ul {
      list-style: none;
      padding: 0;
      margin: 0;

      li {
        color: var(--text-primary);
        font-size: var(--fs-sm);
        line-height: 1.6;
        padding-left: var(--sp-md);
        position: relative;

        &::before {
          content: '•';
          position: absolute;
          left: 0;
          color: var(--accent-ember);
        }
      }
    }
  }
}

.ref-tag {
  margin-right: var(--sp-sm);
  margin-bottom: var(--sp-xs);
}

.feedback-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;

  p {
    color: var(--text-muted);
    font-size: var(--fs-sm);
  }
}
</style>
