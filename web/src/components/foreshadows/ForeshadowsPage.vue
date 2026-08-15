<template>
  <div class="foreshadows-page" v-loading="foreshadowStore.loading">
    <div class="page-content">
      <div class="page-header">
        <h1 class="page-title">伏笔与剧情线</h1>
        <el-button type="primary" size="small" @click="refreshData" :loading="refreshing">
          刷新
        </el-button>
      </div>

      <el-row :gutter="24">
        <el-col :span="14">
          <section class="list-section">
            <span class="section-label">伏笔列表</span>
            <div v-if="foreshadowStore.foreshadows.length" class="items-list">
              <ForeshadowItem
                v-for="f in foreshadowStore.foreshadows"
                :key="f.foreshadow_id"
                :foreshadow="f"
              />
            </div>
            <EmptyState v-else message="暂无伏笔数据，生成完成后自动出现" />
          </section>
        </el-col>
        <el-col :span="10">
          <section class="list-section">
            <span class="section-label">剧情线</span>
            <div v-if="foreshadowStore.plotThreads.length" class="items-list">
              <PlotThreadCard
                v-for="t in foreshadowStore.plotThreads"
                :key="t.thread_id"
                :thread="t"
              />
            </div>
            <EmptyState v-else message="暂无剧情线数据" />
          </section>
        </el-col>
      </el-row>
    </div>
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
.foreshadows-page {
  background: var(--bg-void);
  min-height: 100%;
}

.page-content {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--sp-xl) var(--sp-lg);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-lg);
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  color: var(--text-primary);
  margin: 0;
}

.page-header .el-button--primary {
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%) !important;
  border-color: transparent !important;
}

.list-section {
  display: flex;
  flex-direction: column;
  gap: var(--sp-md);
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-md);
}
</style>
