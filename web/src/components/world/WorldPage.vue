<template>
  <div class="world-page" v-loading="worldStore.loading">
    <template v-if="worldStore.world">
      <div class="world-toolbar ledger-rule">
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

      <!-- Edit mode: raw JSON editor -->
      <div v-if="editing" class="edit-mode">
        <el-input
          v-model="editJson"
          type="textarea"
          :rows="24"
          class="json-editor"
        />
      </div>

      <!-- View mode: ledger sections -->
      <template v-else>
        <el-row :gutter="20">
          <el-col :span="12">
            <PowerSystemCard :world="worldStore.world" />
          </el-col>
          <el-col :span="12">
            <FactionCard :world="worldStore.world" />
          </el-col>
        </el-row>
        <el-row :gutter="20" style="margin-top: var(--sp-lg)">
          <el-col :span="12">
            <LocationCard :world="worldStore.world" />
          </el-col>
          <el-col :span="12">
            <HistoryEventCard :world="worldStore.world" />
          </el-col>
        </el-row>
      </template>
    </template>
    <EmptyState v-else message="暂无世界观数据，请先运行世界观构建" />
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
.world-toolbar {
  display: flex;
  gap: var(--sp-sm);
}

.json-editor {
  :deep(.el-textarea__inner) {
    font-family: var(--font-data);
    font-size: var(--fs-sm);
    line-height: 1.5;
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 1px solid var(--border-rule);
    border-radius: 6px;
  }
}
</style>
