<template>
  <div class="novel-selector">
    <el-select
      v-model="novelStore.activeNovelId"
      placeholder="选择小说"
      size="small"
      @change="onSelect"
      style="width: 200px"
    >
      <el-option
        v-for="n in novelStore.novels"
        :key="n.novel_id"
        :label="n.title"
        :value="n.novel_id"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useNovelStore } from '@/stores/novel'

const novelStore = useNovelStore()

onMounted(() => {
  novelStore.loadNovels()
})

async function onSelect(novelId: string) {
  await novelStore.switchNovel(novelId)
}
</script>

<style scoped lang="scss">
.novel-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
