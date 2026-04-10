<template>
  <div class="control-page">
    <el-row :gutter="20">
      <el-col :span="12">
        <PanelCard title="运行控制" icon="🚀">
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
                type="success"
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
        </PanelCard>
      </el-col>
      <el-col :span="12">
        <PanelCard title="检查点列表" icon="💾">
          <CheckpointList />
        </PanelCard>
      </el-col>
    </el-row>
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <PanelCard title="CLI 参考" icon="⚙️">
          <CliReference />
        </PanelCard>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PanelCard from '@/components/common/PanelCard.vue'
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
.run-control {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.run-status {
  display: flex;
  align-items: center;
  gap: 0.75rem;

  .status-label {
    color: var(--text-muted, #888);
    font-size: 0.9rem;
  }
}

.run-form {
  :deep(.el-form-item) {
    margin-bottom: 0.5rem;
  }
}

.run-actions {
  padding: 0.5rem 0;
}

.progress-display {
  margin-top: 0.5rem;
}
</style>
