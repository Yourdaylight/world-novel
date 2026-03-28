<template>
  <div class="timeline-page" v-loading="loading">
    <!-- Outline Section -->
    <div class="outline-section ledger-rule">
      <div class="outline-header-row">
        <span class="section-label">故事大纲</span>
        <el-button size="small" @click="refreshData">刷新</el-button>
      </div>

      <template v-if="outline">
        <div class="outline-header">
          <h3>{{ outline.title || '未命名' }}</h3>
          <div class="outline-meta">
            <el-tag>{{ outline.genre }}</el-tag>
            <span v-if="outline.theme">主题: {{ outline.theme }}</span>
          </div>
          <p class="outline-premise" v-if="outline.premise">{{ outline.premise }}</p>
          <p class="outline-conflict" v-if="outline.central_conflict">
            <b>核心冲突:</b> {{ outline.central_conflict }}
          </p>
        </div>

        <!-- Volumes -->
        <div v-if="volumes.length > 0" class="volumes-section">
          <div v-for="vol in volumes" :key="vol.volume_index" class="volume-block">
            <div class="volume-header">
              <span class="volume-title">第{{ vol.volume_index + 1 }}卷: {{ vol.title }}</span>
              <span class="volume-range">章节 {{ vol.chapter_start + 1 }}-{{ vol.chapter_end + 1 }}</span>
            </div>
            <p class="volume-desc" v-if="vol.summary">{{ vol.summary }}</p>

            <div
              v-for="ch in chaptersInVolume(vol.volume_index, vol.chapter_start, vol.chapter_end)"
              :key="ch.chapter_index"
              class="chapter-block"
              @click="expandedChapter = expandedChapter === ch.chapter_index ? -1 : ch.chapter_index"
            >
              <div class="chapter-header">
                <span class="ch-index">第{{ ch.chapter_index + 1 }}章</span>
                <span class="ch-title">{{ ch.title }}</span>
                <span class="ch-expand">{{ expandedChapter === ch.chapter_index ? '▼' : '▶' }}</span>
              </div>
              <p class="ch-summary">{{ ch.summary }}</p>
              <div v-if="expandedChapter === ch.chapter_index && ch.scenes" class="scenes-list">
                <div v-for="scene in ch.scenes" :key="scene.scene_index" class="scene-item">
                  <span class="scene-badge">场景{{ scene.scene_index + 1 }}</span>
                  <span class="scene-location">{{ scene.location }}</span>
                  <span class="scene-objective">{{ scene.objective }}</span>
                  <div class="scene-characters" v-if="scene.involved_characters?.length">
                    <el-tag v-for="cid in scene.involved_characters" :key="cid" size="small" type="info">{{ cid }}</el-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Chapters without volumes -->
        <div v-else-if="chapters.length > 0" class="chapters-flat">
          <div
            v-for="ch in chapters"
            :key="ch.chapter_index"
            class="chapter-block"
            @click="expandedChapter = expandedChapter === ch.chapter_index ? -1 : ch.chapter_index"
          >
            <div class="chapter-header">
              <span class="ch-index">第{{ ch.chapter_index + 1 }}章</span>
              <span class="ch-title">{{ ch.title }}</span>
              <span class="ch-expand">{{ expandedChapter === ch.chapter_index ? '▼' : '▶' }}</span>
            </div>
            <p class="ch-summary">{{ ch.summary }}</p>
            <div v-if="expandedChapter === ch.chapter_index && ch.scenes" class="scenes-list">
              <div v-for="scene in ch.scenes" :key="scene.scene_index" class="scene-item">
                <span class="scene-badge">场景{{ scene.scene_index + 1 }}</span>
                <span class="scene-location">{{ scene.location }}</span>
                <span class="scene-objective">{{ scene.objective }}</span>
                <div class="scene-characters" v-if="scene.involved_characters?.length">
                  <el-tag v-for="cid in scene.involved_characters" :key="cid" size="small" type="info">{{ cid }}</el-tag>
                </div>
              </div>
            </div>
          </div>
        </div>

        <EmptyState v-else message="大纲尚未生成，请先在概览页点击「开始创世」" />
      </template>
      <EmptyState v-else message="大纲尚未生成，请先在概览页点击「开始创世」" />
    </div>

    <!-- Vertical Timeline Overview -->
    <div class="timeline-overview" style="margin-bottom: var(--sp-lg)">
      <span class="section-label">时间轴概览</span>
      <HorizontalTimeline
        :events="timelineStore.events"
        :decisions="timelineStore.decisions"
        :total-chapters="chapters.length || progressStore.total"
        :completed-chapters="progressStore.completed"
      />
    </div>

    <!-- Single-column vertical timeline -->
    <div class="timeline-section" style="margin-top: var(--sp-lg)">
      <span class="section-label">时间线</span>
      <template v-if="timelineStore.eras.length">
        <div v-for="era in timelineStore.eras" :key="era.era_id" class="era-section">
          <EraCard
            :era="era"
            :events="eventsForEra(era.era_id)"
            :decisions="decisionsForEra(era)"
          />
        </div>
      </template>
      <EmptyState v-else message="暂无时间线数据，创世后自动生成" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useTimelineStore } from '@/stores/timeline'
import { useWorldStore } from '@/stores/world'
import { onWSEvent } from '@/composables/useWebSocket'
import EmptyState from '@/components/common/EmptyState.vue'
import EraCard from './EraCard.vue'
import HorizontalTimeline from './HorizontalTimeline.vue'
import { useProgressStore } from '@/stores/progress'

const timelineStore = useTimelineStore()
const worldStore = useWorldStore()
const progressStore = useProgressStore()
const loading = ref(false)
const expandedChapter = ref(-1)

const outline = ref<any>(null)
const chapters = ref<any[]>([])
const volumes = ref<any[]>([])

function chaptersInVolume(_volIdx: number, start: number, end: number) {
  return chapters.value.filter(
    (ch) => ch.chapter_index >= start && ch.chapter_index <= end
  )
}

function eventsForEra(eraId: string) {
  return timelineStore.events
    .filter((e) => e.era_id === eraId)
    .sort((a, b) => {
      // Sort by story_time first, fallback to chapter_index
      if (a.story_time && b.story_time && a.story_time !== b.story_time) {
        return a.story_time.localeCompare(b.story_time)
      }
      return (a.chapter_index ?? 0) - (b.chapter_index ?? 0)
    })
}

function decisionsForEra(era: any) {
  return timelineStore.decisions.filter(
    (d) => d.chapter_index >= era.chapter_start && d.chapter_index <= era.chapter_end
  )
}

async function refreshData() {
  loading.value = true
  await Promise.all([worldStore.loadWorld(), timelineStore.loadAll()])
  parseOutline()
  loading.value = false
}

function parseOutline() {
  outline.value = worldStore.outline
  volumes.value = worldStore.volumes || []
  if (worldStore.outline && (worldStore.outline as any).chapters) {
    chapters.value = (worldStore.outline as any).chapters
  } else {
    chapters.value = []
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([worldStore.loadWorld(), timelineStore.loadAll()])
  parseOutline()
  loading.value = false
})

// Auto-refresh on WS timeline events
const unsub = onWSEvent('timeline_updated', () => {
  timelineStore.loadAll()
})
onUnmounted(() => unsub())
</script>

<style scoped lang="scss">
.outline-section {
  padding-bottom: var(--sp-lg);
}

.outline-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-md);
}

.outline-header {
  margin-bottom: var(--sp-lg);

  h3 {
    font-family: var(--font-ui);
    font-size: var(--fs-lg);
    font-weight: 600;
    margin: 0 0 var(--sp-sm);
    color: var(--text-primary);
  }
  .outline-meta {
    display: flex;
    align-items: center;
    gap: var(--sp-md);
    margin-bottom: var(--sp-sm);
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .outline-premise {
    line-height: 1.7;
    color: var(--text-primary);
    margin: var(--sp-sm) 0;
  }
  .outline-conflict {
    line-height: 1.7;
    color: var(--text-secondary);
    margin: 0;
  }
}

.volume-block {
  margin-bottom: var(--sp-lg);

  .volume-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--sp-sm) 0;
    border-bottom: 1px solid var(--border-rule);

    .volume-title {
      font-weight: 600;
      font-size: var(--fs-md);
      color: var(--accent-aurora);
    }
    .volume-range {
      font-family: var(--font-data);
      font-size: var(--fs-xs);
      color: var(--text-muted);
    }
  }
  .volume-desc {
    font-size: var(--fs-sm);
    color: var(--text-secondary);
    margin: var(--sp-sm) 0 var(--sp-md);
    line-height: 1.7;
  }
}

.chapter-block {
  padding: var(--sp-sm) 0;
  cursor: pointer;
  border-bottom: 1px solid var(--border-ghost);
  border-left: 3px solid transparent;
  padding-left: var(--sp-sm);

  &:hover {
    border-left-color: var(--accent-ember);
  }

  .chapter-header {
    display: flex;
    align-items: center;
    gap: var(--sp-sm);

    .ch-index {
      font-family: var(--font-data);
      font-weight: 600;
      font-size: var(--fs-xs);
      color: var(--accent-ember);
      min-width: 4rem;
    }
    .ch-title {
      font-weight: 500;
      color: var(--text-primary);
      flex: 1;
    }
    .ch-expand {
      font-size: var(--fs-xs);
      color: var(--text-muted);
    }
  }
  .ch-summary {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    line-height: 1.5;
    margin: var(--sp-xs) 0 0;
  }
}

.scenes-list {
  margin-top: var(--sp-sm);
  padding-left: var(--sp-md);
  border-left: 1px solid var(--border-rule);

  .scene-item {
    padding: var(--sp-xs) 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--sp-sm);
    align-items: center;
    font-size: var(--fs-xs);
    border-bottom: 1px solid var(--border-ghost);

    &:last-child { border-bottom: none; }

    .scene-badge {
      font-weight: 600;
      color: var(--text-muted);
    }
    .scene-location {
      color: var(--accent-jade);
    }
    .scene-objective {
      color: var(--text-primary);
      flex: 1;
      min-width: 150px;
    }
    .scene-characters {
      display: flex;
      gap: var(--sp-2xs);
      flex-wrap: wrap;
      width: 100%;
    }
  }
}

.timeline-section {
  padding-bottom: var(--sp-lg);
}

.era-section {
  margin-bottom: var(--sp-md);
}
</style>
