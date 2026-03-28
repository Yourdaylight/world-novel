<template>
  <div class="scene-timeline" v-if="scenes.length > 0">
    <div class="timeline-toggle" @click="expanded = !expanded">
      <span class="toggle-icon">{{ expanded ? '▾' : '▸' }}</span>
      <span class="toggle-label">场景时间线</span>
      <span class="toggle-count">{{ scenes.length }} 场景</span>
    </div>

    <div class="timeline-body" v-if="expanded">
      <div class="timeline-track">
        <div
          v-for="(scene, idx) in scenes"
          :key="scene.scene_index"
          class="timeline-node"
          :class="{ active: scene.scene_index === activeSceneIndex }"
          @click="$emit('select-scene', scene.scene_index)"
        >
          <!-- Connector line -->
          <div class="node-connector" v-if="idx < scenes.length - 1"></div>

          <!-- Node dot -->
          <div class="node-dot">
            <span class="dot-index">{{ scene.scene_index }}</span>
          </div>

          <!-- Node content -->
          <div class="node-content">
            <div class="node-header">
              <span class="node-location" v-if="scene.location">📍 {{ scene.location }}</span>
              <span class="node-tone" v-if="scene.tone">{{ scene.tone }}</span>
            </div>

            <p class="node-objective" v-if="scene.objective">
              🎯 {{ scene.objective }}
            </p>
            <p class="node-conflict" v-if="scene.conflict">
              ⚔️ {{ scene.conflict }}
            </p>

            <!-- Characters -->
            <div class="node-characters" v-if="scene.involved_characters.length">
              <span
                v-for="char in scene.involved_characters"
                :key="char"
                class="char-tag"
              >{{ char }}</span>
            </div>

            <!-- Foreshadows -->
            <div class="node-foreshadows" v-if="scene.foreshadows_to_plant.length || scene.foreshadows_to_payoff.length">
              <span
                v-for="f in scene.foreshadows_to_plant"
                :key="'plant-' + f"
                class="foreshadow-tag plant"
                title="伏笔植入"
              >🌱 {{ f }}</span>
              <span
                v-for="f in scene.foreshadows_to_payoff"
                :key="'payoff-' + f"
                class="foreshadow-tag payoff"
                title="伏笔揭示"
              >🔮 {{ f }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { SceneBeat } from '@/api/types'

defineProps<{
  scenes: SceneBeat[]
  activeSceneIndex: number | null
}>()

defineEmits<{
  (e: 'select-scene', sceneIndex: number): void
}>()

const expanded = ref(false)
</script>

<style scoped lang="scss">
.scene-timeline {
  border-top: 1px solid var(--border-rule);
  margin-top: var(--sp-lg);
}

.timeline-toggle {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-sm) 0;
  cursor: pointer;
  user-select: none;

  &:hover .toggle-label {
    color: var(--text-primary);
  }
}

.toggle-icon {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  width: 12px;
}

.toggle-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: color 0.15s;
}

.toggle-count {
  font-family: var(--font-data);
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.timeline-body {
  padding: var(--sp-md) 0 var(--sp-sm) 0;
}

.timeline-track {
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
  padding-left: var(--sp-lg);
}

.timeline-node {
  position: relative;
  padding-bottom: var(--sp-lg);
  cursor: pointer;

  &:last-child {
    padding-bottom: 0;

    .node-connector {
      display: none;
    }
  }

  &:hover .node-content {
    background: var(--bg-elevated);
  }

  &.active {
    .node-dot {
      background: var(--accent-ember);
      border-color: var(--accent-ember);
      box-shadow: var(--glow-ember);
    }

    .node-content {
      border-left-color: var(--accent-ember);
    }
  }
}

.node-connector {
  position: absolute;
  left: -17px;
  top: 20px;
  bottom: 0;
  width: 1px;
  background: var(--border-rule);
}

.node-dot {
  position: absolute;
  left: -24px;
  top: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 2px solid var(--accent-aurora);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;

  .dot-index {
    font-family: var(--font-data);
    font-size: 8px;
    color: var(--text-primary);
    font-weight: 600;
  }
}

.node-content {
  padding: var(--sp-sm) var(--sp-md);
  border-left: 2px solid transparent;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  transition: background 0.15s;
}

.node-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-xs);
}

.node-location {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.node-tone {
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--bg-glass);
}

.node-objective,
.node-conflict {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  line-height: 1.5;
  margin: var(--sp-2xs) 0;
}

.node-conflict {
  color: var(--accent-cinnabar);
  opacity: 0.8;
}

.node-characters {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: var(--sp-xs);
}

.char-tag {
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--text-secondary);
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(166, 127, 212, 0.12);
}

.node-foreshadows {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: var(--sp-xs);
}

.foreshadow-tag {
  font-family: var(--font-ui);
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  &.plant {
    color: var(--accent-jade);
    background: rgba(78, 201, 148, 0.1);
  }

  &.payoff {
    color: var(--accent-aurora);
    background: rgba(166, 127, 212, 0.1);
  }
}
</style>
