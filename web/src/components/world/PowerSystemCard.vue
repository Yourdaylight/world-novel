<template>
  <PanelCard title="力量体系" icon="⚡">
    <template v-if="systems.length">
      <div v-for="(ps, idx) in systems" :key="idx" class="power-block">
        <div class="power-name">{{ ps.name }}</div>
        <p class="power-desc">{{ ps.description }}</p>
        <div v-if="ps.levels && ps.levels.length" class="power-levels">
          <h4>等级体系</h4>
          <div v-for="(level, i) in ps.levels" :key="i" class="level-item">
            <el-tag size="small" :type="i < 3 ? 'primary' : 'info'">
              {{ typeof level === 'string' ? level : level.name || JSON.stringify(level) }}
            </el-tag>
          </div>
        </div>
        <div v-if="ps.rules" class="power-rules">
          <h4>规则</h4>
          <ul>
            <li v-for="(rule, i) in toArray(ps.rules)" :key="i">
              {{ typeof rule === 'string' ? rule : JSON.stringify(rule) }}
            </li>
          </ul>
        </div>
      </div>
    </template>
    <EmptyState v-else message="暂无力量体系数据" icon="⚡" />
  </PanelCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PanelCard from '@/components/common/PanelCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { WorldData } from '@/api/types'

const props = defineProps<{ world: WorldData }>()

const systems = computed(() => {
  // Support both power_systems (array) and power_system (object)
  const w = props.world
  if (Array.isArray(w.power_systems) && w.power_systems.length) return w.power_systems
  if (w.power_system) return Array.isArray(w.power_system) ? w.power_system : [w.power_system]
  return []
})

function toArray(val: any): any[] {
  if (Array.isArray(val)) return val
  if (val) return [val]
  return []
}
</script>

<style scoped lang="scss">
.power-block {
  margin-bottom: var(--sp-lg);
  padding-bottom: var(--sp-md);
  border-bottom: 1px solid var(--border-rule);

  &:last-child { border-bottom: none; margin-bottom: 0; }
}

.power-name {
  font-family: var(--font-ui);
  font-size: var(--fs-lg);
  font-weight: 400;
  color: var(--accent-ember);
  margin-bottom: var(--sp-sm);
}

.power-desc {
  font-family: var(--font-ui);
  color: var(--text-secondary);
  line-height: 1.85;
  margin-bottom: var(--sp-md);
  font-size: var(--fs-sm);
}

.power-levels {
  margin-bottom: var(--sp-md);

  h4 {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: var(--sp-sm);
  }
  .level-item { display: inline-block; margin: var(--sp-2xs) var(--sp-xs) var(--sp-2xs) 0; }
}

.power-rules {
  h4 {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: var(--sp-sm);
  }
  ul {
    padding-left: var(--sp-lg);
    color: var(--text-secondary);
    font-family: var(--font-ui);
    line-height: 1.85;
    font-size: var(--fs-sm);
  }
}
</style>
