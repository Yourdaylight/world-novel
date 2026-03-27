<template>
  <PanelCard title="小说信息" icon="📖">
    <template v-if="worldStore.outline">
      <div class="info-grid">
        <div class="info-item">
          <label>标题</label>
          <span class="info-value">{{ worldStore.outline.title || '未命名' }}</span>
        </div>
        <div class="info-item">
          <label>类型</label>
          <span class="info-value">{{ worldStore.outline.genre || '—' }}</span>
        </div>
        <div class="info-item" v-if="worldStore.outline.themes">
          <label>主题</label>
          <span class="info-value">{{ (worldStore.outline.themes as string[]).join('、') }}</span>
        </div>
        <div class="info-item" v-if="progressStore.total">
          <label>进度</label>
          <span class="info-value data">{{ progressStore.completed }} / {{ progressStore.total }} 章</span>
        </div>
      </div>
      <div class="synopsis" v-if="worldStore.outline.synopsis">
        <label>故事梗概</label>
        <p>{{ worldStore.outline.synopsis }}</p>
      </div>
    </template>
    <EmptyState v-else message="暂无小说大纲数据" />
  </PanelCard>
</template>

<script setup lang="ts">
import PanelCard from '@/components/common/PanelCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useWorldStore } from '@/stores/world'
import { useProgressStore } from '@/stores/progress'

const worldStore = useWorldStore()
const progressStore = useProgressStore()
</script>

<style scoped lang="scss">
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-md);
  margin-bottom: var(--sp-md);
}
.info-item {
  padding-bottom: var(--sp-sm);
  border-bottom: 1px solid var(--border-ghost);

  label {
    display: block;
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: var(--sp-xs);
  }
  .info-value {
    font-family: var(--font-ui);
    font-size: var(--fs-base);
    color: var(--text-primary);

    &.data {
      font-family: var(--font-data);
      font-size: var(--fs-sm);
    }
  }
}
.synopsis {
  padding-top: var(--sp-sm);
  border-top: 1px solid var(--border-rule);

  label {
    display: block;
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: var(--sp-sm);
  }
  p {
    font-family: var(--font-ui);
    color: var(--text-primary);
    line-height: 1.85;
    font-size: var(--fs-base);
  }
}
</style>
