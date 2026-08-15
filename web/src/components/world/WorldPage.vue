<template>
  <div class="world-page" v-loading="worldStore.loading">
    <template v-if="worldStore.world">
      <header class="page-header">
        <h1 class="page-title">世界观</h1>
        <div class="page-actions">
          <el-button v-if="!editing" type="primary" plain size="small" @click="startEdit">
            ✏️ 编辑世界观
          </el-button>
          <template v-if="editing">
            <el-button type="success" size="small" :loading="saving" @click="onSave">
              💾 保存
            </el-button>
            <el-button size="small" @click="cancelEdit">取消</el-button>
          </template>
        </div>
      </header>

      <!-- Edit mode: raw JSON editor -->
      <div v-if="editing" class="card edit-card">
        <el-input
          v-model="editJson"
          type="textarea"
          :rows="24"
          class="json-editor"
        />
      </div>

      <!-- View mode: cards grid -->
      <div v-else class="cards-grid">
        <PowerSystemCard :world="worldStore.world" />
        <FactionCard :world="worldStore.world" />
        <LocationCard :world="worldStore.world" />
        <HistoryEventCard :world="worldStore.world" />
      </div>
    </template>
    <EmptyState v-else message="暂无世界观数据，请先运行世界观构建" class="compact-empty" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorldStore } from '@/stores/world'
import { saveWorld } from '@/api/novels'
import EmptyState from '@/components/common/EmptyState.vue'
import PowerSystemCard from './PowerSystemCard.vue'
import FactionCard from './FactionCard.vue'
import LocationCard from './LocationCard.vue'
import HistoryEventCard from './HistoryEventCard.vue'

const worldStore = useWorldStore()
const editing = ref(false)
const saving = ref(false)
const editJson = ref('')

onMounted(() => {
  if (!worldStore.world) worldStore.loadWorld()
})

function startEdit() {
  editJson.value = JSON.stringify(worldStore.world, null, 2)
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  editJson.value = ''
}

async function onSave() {
  try {
    const parsed = JSON.parse(editJson.value)
    saving.value = true
    const res = await saveWorld(parsed)
    if (res.ok) {
      ElMessage.success('世界观已保存')
      editing.value = false
      await worldStore.loadWorld()
    } else {
      ElMessage.error('保存失败')
    }
  } catch (e) {
    ElMessage.error('JSON 格式错误')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.world-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--sp-xl) var(--sp-lg);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
  flex-wrap: wrap;
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-2xl);
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  margin: 0;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--sp-lg);
  align-items: stretch;
}

.edit-card {
  padding: var(--sp-md);
}

.json-editor {
  :deep(.el-textarea__inner) {
    font-family: var(--font-data);
    font-size: var(--fs-sm);
    line-height: 1.5;
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 1px solid var(--border-rule);
    border-radius: var(--radius-md);
  }
}

:deep(.empty-state.compact-empty) {
  padding: var(--sp-lg) var(--sp-md);
}

@media (max-width: 768px) {
  .world-page {
    padding: var(--sp-lg) var(--sp-md);
  }

  .cards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
