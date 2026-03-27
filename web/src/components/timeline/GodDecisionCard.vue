<template>
  <div class="god-decision-card">
    <div class="decision-header">
      <span class="decision-chapter">第{{ decision.chapter_index + 1 }}章后</span>
    </div>

    <!-- 世界事件 -->
    <div class="decision-section" v-if="decision.world_events?.length">
      <h5>世界事件</h5>
      <div v-for="(we, i) in decision.world_events" :key="i" class="world-event">
        <div class="we-header">
          <el-tag size="small" type="warning">{{ we.event_type }}</el-tag>
          <span class="we-title">{{ we.title }}</span>
          <span class="we-time" v-if="we.story_time">{{ we.story_time }}</span>
        </div>
        <p class="we-desc">{{ we.description }}</p>
        <div class="we-chars" v-if="we.affected_characters?.length">
          <el-tag v-for="c in we.affected_characters" :key="c" size="small" type="info">{{ c }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 支线触发 -->
    <div class="decision-section" v-if="decision.subplot_triggers?.length">
      <h5>支线触发</h5>
      <div v-for="(st, i) in decision.subplot_triggers" :key="i" class="subplot-trigger">
        <el-tag size="small">{{ st.trigger_type }}</el-tag>
        <p>{{ st.description }}</p>
      </div>
    </div>

    <!-- 下章指引 -->
    <div class="decision-section guidance" v-if="decision.next_chapter_guidance">
      <h5>下章叙事指引</h5>
      <p>{{ truncateText(decision.next_chapter_guidance, 300) }}</p>
    </div>

    <!-- 时间推进 -->
    <div class="decision-section" v-if="decision.time_progression?.description">
      <h5>时间推进</h5>
      <p>{{ decision.time_progression.description }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ decision: any }>()

function truncateText(text: string, max: number) {
  return text.length > max ? text.slice(0, max) + '...' : text
}
</script>

<style scoped lang="scss">
.god-decision-card {
  padding: var(--sp-md) 0 var(--sp-md) var(--sp-md);
  background: rgba(224, 69, 69, 0.04);
  border-radius: 6px;
  margin-bottom: var(--sp-md);
  border-left: 3px solid var(--accent-cinnabar);
  border-bottom: 1px solid var(--border-rule);
}

.decision-header {
  margin-bottom: var(--sp-sm);
  .decision-chapter {
    font-family: var(--font-data);
    font-weight: 600;
    font-size: var(--fs-sm);
    color: var(--accent-cinnabar);
  }
}

.decision-section {
  margin-bottom: var(--sp-sm);

  h5 {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin: 0 0 var(--sp-xs);
  }
  p {
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    color: var(--text-primary);
    line-height: 1.85;
    margin: var(--sp-2xs) 0;
  }

  &.guidance {
    background: rgba(212, 121, 58, 0.04);
    padding: var(--sp-sm);
    border-left: 2px solid var(--accent-ember);
    margin-left: calc(-1 * var(--sp-md));
    padding-left: var(--sp-md);
  }
}

.world-event {
  margin-bottom: var(--sp-sm);
  padding-bottom: var(--sp-sm);
  border-bottom: 1px solid var(--border-ghost);

  &:last-child { border-bottom: none; }

  .we-header {
    display: flex;
    align-items: center;
    gap: var(--sp-sm);
    flex-wrap: wrap;
    margin-bottom: var(--sp-2xs);
  }
  .we-title {
    font-family: var(--font-ui);
    font-weight: 500;
    font-size: var(--fs-sm);
    color: var(--text-primary);
  }
  .we-time {
    font-family: var(--font-data);
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .we-desc {
    font-size: var(--fs-xs);
  }
  .we-chars {
    display: flex;
    gap: var(--sp-2xs);
    flex-wrap: wrap;
    margin-top: var(--sp-xs);
  }
}

.subplot-trigger {
  margin-bottom: var(--sp-sm);
  p { margin-top: var(--sp-2xs); font-size: var(--fs-xs); }
}
</style>
