<template>
  <div class="control-page page-container">
    <header class="page-header">
      <h1 class="page-title">控制台</h1>
      <span class="page-subtitle">运行控制与检查点管理</span>
    </header>

    <div class="page-content">
      <div class="control-grid">
        <section class="card control-card">
          <h3 class="section-label">运行控制</h3>
          <div class="run-control">
            <div class="run-status">
              <span class="status-label">当前状态：</span>
              <el-tag :type="statusType" size="large">{{ statusText }}</el-tag>
            </div>

            <el-form label-position="left" class="run-form">
              <el-form-item label="运行模式">
                <el-tag type="info" size="small">解耦模式</el-tag>
              </el-form-item>
            </el-form>

            <div class="run-actions">
              <el-button
                v-if="progressStore.phase === 'idle' || progressStore.phase === 'error'"
                type="primary"
                size="large"
                :loading="starting"
                @click="onStartGeneration"
              >
                ▶ 开始运行
              </el-button>
              <el-button
                v-else-if="progressStore.phase === 'done'"
                type="info"
                size="large"
                disabled
              >
                ✅ 已完成
              </el-button>
              <el-tag v-else type="primary" size="large" effect="plain">
                🔄 运行中... ({{ progressStore.phase }})
              </el-tag>
            </div>

            <div class="progress-display" v-if="progressStore.total > 0">
              <el-progress
                :percentage="progressStore.percent"
                :stroke-width="12"
                :format="() => `${progressStore.completed}/${progressStore.total} 章`"
              />
            </div>
          </div>
        </section>

        <section class="card control-card">
          <h3 class="section-label">检查点列表</h3>
          <CheckpointList />
        </section>
      </div>

      <section class="card cli-card">
        <h3 class="section-label">CLI 参考</h3>
        <CliReference />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import CliReference from './CliReference.vue'
import CheckpointList from './CheckpointList.vue'
import { useProgressStore } from '@/stores/progress'
import { startGeneration } from '@/api/novels'

const route = useRoute()
const progressStore = useProgressStore()

const runMode = ref('decoupled')
const starting = ref(false)

const statusText = computed(() => {
  const phaseMap: Record<string, string> = {
    idle: '待运行',
    directing: '规划中',
    world_building: '构建世界',
    foreshadow_planning: '规划伏笔',
    simulating: '模拟场景',
    writing: '写作中',
    reviewing: '审校中',
    god_deliberation: '命运裁决',
    done: '已完成',
    error: '出错',
  }
  return phaseMap[progressStore.phase] || progressStore.phase
})

const statusType = computed(() => {
  const typeMap: Record<string, string> = {
    idle: 'info',
    done: 'success',
    error: 'danger',
  }
  return (typeMap[progressStore.phase] || 'primary') as any
})

async function onStartGeneration() {
  const novelId = route.params.novelId as string
  if (!novelId) {
    ElMessage.warning('未选择世界')
    return
  }

  starting.value = true
  try {
    const res = await startGeneration(novelId, runMode.value)
    if (res.ok) {
      ElMessage.success('生成已启动')
    } else {
      ElMessage.error(res.error || '启动失败')
    }
  } finally {
    starting.value = false
  }
}
</script>

<style scoped lang="scss">
.page-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 var(--sp-lg);
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

.page-content {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
}

.card {
  padding: var(--sp-lg);
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--sp-lg);
}

.run-control {
  display: flex;
  flex-direction: column;
  gap: var(--sp-md);
}

.run-status {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);

  .status-label {
    color: var(--text-muted);
    font-size: var(--fs-sm);
  }
}

.run-form {
  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.run-actions {
  padding: var(--sp-xs) 0;
}

.progress-display {
  margin-top: var(--sp-xs);
}

@media (max-width: 768px) {
  .page-container {
    padding: 0 var(--sp-md);
  }

  .control-grid {
    grid-template-columns: 1fr;
  }
}
</style>
