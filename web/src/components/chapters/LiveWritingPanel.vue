<template>
  <div class="live-writing-panel" v-if="liveWritingStore.isWriting">
    <div class="live-section ledger-rule">
      <span class="section-label">实时创作</span>
      <div class="live-info">
        <el-tag type="success" effect="dark">正在创作</el-tag>
        <span v-if="liveWritingStore.currentChapter !== null">第{{ liveWritingStore.currentChapter + 1 }}章</span>
        <span v-if="liveWritingStore.currentPhase">{{ liveWritingStore.currentPhase }}</span>
      </div>
      <div class="live-text" v-if="liveWritingStore.liveText">
        {{ liveWritingStore.liveText }}
        <span class="cursor-blink">|</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useLiveWritingStore } from '@/stores/liveWriting'

const liveWritingStore = useLiveWritingStore()
</script>

<style scoped lang="scss">
.live-writing-panel {
  margin-top: var(--sp-md);
}
.live-section {
  padding: var(--sp-md) 0;
}
.live-info {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-md);

  span {
    font-family: var(--font-data);
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
}
.live-text {
  background: var(--bg-surface);
  border: 1px solid var(--border-rule);
  border-radius: 6px;
  padding: var(--sp-md);
  font-family: var(--font-ui);
  font-size: var(--fs-md);
  line-height: 2.0;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  color: var(--text-primary);
}
.cursor-blink {
  animation: blink 1s infinite;
  color: var(--accent-ember);
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
