<template>
  <div class="scene-outline-bar" v-if="scenes.length > 0">
    <div class="bar-header">
      <span class="bar-label">场景结构</span>
      <span class="bar-count">{{ scenes.length }} 个场景</span>
    </div>
    <div class="bar-cards">
      <div
        v-for="scene in scenes"
        :key="scene.scene_index"
        class="scene-card"
        :class="{ active: scene.scene_index === activeSceneIndex }"
        @click="onSceneClick(scene.scene_index)"
      >
        <div class="card-top">
          <span class="card-index">场景 {{ scene.scene_index }}</span>
          <span class="card-tone" v-if="scene.tone">{{ scene.tone }}</span>
        </div>
        <div class="card-location" v-if="scene.location">📍 {{ scene.location }}</div>
        <div class="card-objective" v-if="scene.objective">{{ scene.objective }}</div>
        <div class="card-characters" v-if="scene.involved_characters.length">
          <span
            v-for="char in scene.involved_characters"
            :key="char"
            class="char-chip"
          >{{ char }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SceneBeat } from '@/api/types'

const props = defineProps<{
  scenes: SceneBeat[]
  activeSceneIndex: number | null
}>()

const emit = defineEmits<{
  (e: 'select-scene', sceneIndex: number): void
}>()

function onSceneClick(sceneIndex: number) {
  emit('select-scene', sceneIndex)
}
</script>

<style scoped lang="scss">
.scene-outline-bar {
  margin-bottom: var(--sp-lg);
}

.bar-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-sm);
}

.bar-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.bar-count {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.bar-cards {
  display: flex;
  gap: var(--sp-sm);
  overflow-x: auto;
  padding-bottom: var(--sp-xs);

  &::-webkit-scrollbar {
    height: 3px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--border-rule);
    border-radius: 2px;
  }
}

.scene-card {
  flex: 0 0 auto;
  min-width: 180px;
  max-width: 240px;
  padding: var(--sp-sm) var(--sp-md);
  border: 1px solid var(--border-ghost);
  border-bottom: 2px solid transparent;
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  cursor: pointer;
  transition: border-color 0.15s;

  &:hover {
    border-color: var(--border-rule);
  }

  &.active {
    border-bottom-color: var(--accent-ember);
    background: var(--bg-elevated);
  }
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-xs);
}

.card-index {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--accent-aurora);
}

.card-tone {
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--bg-glass);
}

.card-location {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  margin-bottom: var(--sp-2xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-objective {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-muted);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: var(--sp-xs);
}

.card-characters {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.char-chip {
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--text-secondary);
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(166, 127, 212, 0.12);
}
</style>
