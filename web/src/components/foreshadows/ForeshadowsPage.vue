<template>
  <div class="foreshadows-page" v-loading="foreshadowStore.loading">
    <div class="page-header">
      <span class="section-label" style="margin-bottom: 0;">伏笔与剧情线</span>
      <el-button size="small" @click="refreshData" :loading="refreshing">
        刷新
      </el-button>
    </div>

    <el-row :gutter="20">
      <el-col :span="14">
        <div class="ledger-zone">
          <span class="section-label">伏笔列表</span>
          <template v-if="foreshadowStore.foreshadows.length">
            <ForeshadowItem
              v-for="f in foreshadowStore.foreshadows"
              :key="f.foreshadow_id"
              :foreshadow="f"
            />
          </template>
          <EmptyState v-else message="暂无伏笔数据，生成完成后自动出现" />
        </div>
      </el-col>
      <el-col :span="10">
        <div class="ledger-zone">
          <span class="section-label">剧情线</span>
          <template v-if="foreshadowStore.plotThreads.length">
            <PlotThreadCard
              v-for="t in foreshadowStore.plotThreads"
              :key="t.thread_id"
              :thread="t"
            />
          </template>
          <EmptyState v-else message="暂无剧情线数据" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useForeshadowStore } from '@/stores/foreshadows'
import { onWSEvent } from '@/composables/useWebSocket'
import EmptyState from '@/components/common/EmptyState.vue'
import ForeshadowItem from './ForeshadowItem.vue'
import PlotThreadCard from './PlotThreadCard.vue'

const foreshadowStore = useForeshadowStore()
const route = useRoute()
const refreshing = ref(false)

async function refreshData() {
  refreshing.value = true
  await foreshadowStore.loadAll()
  refreshing.value = false
}

onMounted(() => {
  foreshadowStore.loadAll()
})

// Auto-reload when route changes (switching novels)
watch(() => route.params.novelId, () => {
  foreshadowStore.loadAll()
})

// Auto-reload on WebSocket event
const unsub = onWSEvent('foreshadows_updated', () => {
  foreshadowStore.loadAll()
})
onUnmounted(() => unsub())
</script>

<style scoped lang="scss">
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-md);
}

.ledger-zone {
  padding-bottom: var(--sp-lg);
}
</style>
