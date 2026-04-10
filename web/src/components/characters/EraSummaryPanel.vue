<template>
  <div class="era-summary-panel" v-loading="loading">
    <div v-if="summaries.length > 0">
      <div class="panel-header">
        <span class="section-label">时代摘要 ({{ summaries.length }})</span>
        <el-button size="small" @click="handleConsolidate" :loading="consolidating">
          整合冷却记忆
        </el-button>
      </div>
      <el-collapse>
        <el-collapse-item
          v-for="s in summaries"
          :key="s.summary_id"
          :name="s.summary_id"
        >
          <template #title>
            <div class="era-title">
              <span class="era-range">第{{ s.chapter_start + 1 }}-{{ s.chapter_end + 1 }}章</span>
              <el-tag size="small" type="info">{{ s.source_memory_count }}条记忆</el-tag>
            </div>
          </template>
          <p class="era-content">{{ s.summary }}</p>
          <span class="era-time">{{ s.created_at }}</span>
        </el-collapse-item>
      </el-collapse>
    </div>
    <div v-else-if="!loading" class="empty-hint">
      <span>暂无时代摘要</span>
      <el-button size="small" text @click="handleConsolidate" :loading="consolidating">
        尝试整合
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchEraSummaries, triggerConsolidate } from '@/api/memory'
import type { EraSummary } from '@/api/types'

const props = defineProps<{ characterId: string }>()

const loading = ref(false)
const consolidating = ref(false)
const summaries = ref<EraSummary[]>([])

async function load() {
  loading.value = true
  try {
    const data = await fetchEraSummaries(props.characterId)
    summaries.value = data.summaries || []
  } finally {
    loading.value = false
  }
}

async function handleConsolidate() {
  consolidating.value = true
  try {
    const res = await triggerConsolidate(props.characterId)
    if (res.ok && res.summary_id) {
      ElMessage.success('记忆整合完成')
      await load()
    } else {
      ElMessage.info(res.message || '冷却记忆不足，暂无需整合')
    }
  } catch {
    ElMessage.error('整合失败')
  } finally {
    consolidating.value = false
  }
}

onMounted(() => load())
watch(() => props.characterId, () => load())
</script>

<style scoped lang="scss">
.era-summary-panel {
  margin-top: var(--sp-md);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-sm);
}
.era-title {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
}
.era-range {
  font-family: var(--font-data);
  font-size: var(--fs-sm);
  color: var(--accent-ember);
  font-weight: 600;
}
.era-content {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  line-height: 1.85;
  color: var(--text-primary);
  margin: 0 0 var(--sp-xs) 0;
}
.era-time {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}
.empty-hint {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  color: var(--text-muted);
  font-size: var(--fs-sm);
  padding: var(--sp-md) 0;
}
</style>
