<template>
  <div class="character-profile">
    <!-- Header -->
    <div class="profile-header ledger-rule">
      <h3>{{ character.name }}</h3>
      <el-tag>{{ character.role }}</el-tag>
      <div class="profile-stats" v-if="fullProfile">
        <span>💬 {{ fullProfile.stats.action_types?.dialogue || 0 }} 对话</span>
        <span>💭 {{ fullProfile.stats.action_types?.thought || 0 }} 思考</span>
        <span>⚡ {{ fullProfile.stats.action_types?.behavior || 0 }} 行动</span>
        <span>🔄 {{ fullProfile.stats.action_types?.reaction || 0 }} 反应</span>
        <span>🧠 {{ fullProfile.stats.total_memories || 0 }} 记忆</span>
      </div>
    </div>

    <!-- Emotion Radar -->
    <div class="profile-section" v-if="fullProfile?.latest_emotion">
      <span class="section-label">当前情感状态</span>
      <div class="emotion-bars">
        <div v-for="(val, key) in fullProfile.latest_emotion" :key="String(key)" class="emotion-bar">
          <span class="emo-label">{{ emotionLabels[String(key)] || key }}</span>
          <el-progress
            :percentage="Math.round((Number(val) + 1) * 50)"
            :stroke-width="8"
            :show-text="false"
            :color="Number(val) >= 0 ? '#4ec994' : '#e04545'"
          />
          <span class="emo-value">{{ Number(val).toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- Backstory -->
    <div class="profile-section" v-if="character.backstory">
      <span class="section-label">背景故事</span>
      <p class="backstory-text">{{ character.backstory }}</p>
    </div>

    <!-- Relationships -->
    <div class="profile-section" v-if="fullProfile?.relationships?.length">
      <span class="section-label">人际关系</span>
      <div class="rel-table">
        <div v-for="(rel, i) in fullProfile.relationships" :key="i" class="rel-row">
          <span class="rel-target">{{ rel.source_id === character.id ? rel.target_id : rel.source_id }}</span>
          <el-tag size="small" type="info">{{ rel.relationship_type }}</el-tag>
          <span class="rel-scores">
            信任 <b :style="{ color: rel.trust >= 0 ? 'var(--accent-jade)' : 'var(--accent-cinnabar)' }">{{ rel.trust.toFixed(1) }}</b>
            好感 <b :style="{ color: rel.affection >= 0 ? 'var(--accent-jade)' : 'var(--accent-cinnabar)' }">{{ rel.affection.toFixed(1) }}</b>
          </span>
          <span class="rel-desc" v-if="rel.description">{{ rel.description }}</span>
        </div>
      </div>
    </div>

    <!-- Tabs: Actions / Memories / Emotion Arc -->
    <div class="profile-section">
      <el-tabs v-model="activeTab" type="border-card" class="detail-tabs">
        <!-- Action Timeline -->
        <el-tab-pane label="📜 行动记录" name="actions">
          <div v-if="actionsLoading" v-loading="true" style="min-height: 200px" />
          <div v-else-if="allActions.length === 0" class="empty-hint">暂无行动记录</div>
          <div v-else class="action-timeline">
            <template v-for="(group, chKey) in actionsByChapter" :key="chKey">
              <div class="chapter-group">
                <div class="chapter-label">第 {{ Number(chKey) + 1 }} 章</div>
                <div
                  v-for="(action, i) in group"
                  :key="i"
                  :class="['action-item', `type-${action.action_type}`]"
                >
                  <span class="action-icon">{{ actionIcons[action.action_type] || '•' }}</span>
                  <div class="action-body">
                    <div class="action-meta">
                      <el-tag size="small" :type="actionTagType(action.action_type)">
                        {{ actionTypeLabel(action.action_type) }}
                      </el-tag>
                      <span class="scene-badge">场景{{ action.scene_index + 1 }}</span>
                      <span v-if="action.target" class="target-badge">→ {{ action.target }}</span>
                    </div>
                    <div class="action-content">{{ action.content }}</div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </el-tab-pane>

        <!-- Episodic Memories -->
        <el-tab-pane label="🧠 记忆" name="memories">
          <div v-if="memoriesLoading" v-loading="true" style="min-height: 200px" />
          <div v-else-if="allMemories.length === 0" class="empty-hint">暂无记忆</div>
          <div v-else class="memory-list">
            <div v-for="mem in allMemories" :key="mem.memory_id" class="memory-item">
              <div class="memory-meta">
                <span>第{{ mem.chapter_index + 1 }}章 场景{{ mem.scene_index + 1 }}</span>
                <el-tag v-if="mem.importance >= 0.7" size="small" type="warning">重要</el-tag>
                <span class="valence" :style="{ color: mem.emotional_valence >= 0 ? 'var(--accent-jade)' : 'var(--accent-cinnabar)' }">
                  {{ mem.emotional_valence >= 0 ? '😊' : '😞' }} {{ mem.emotional_valence.toFixed(1) }}
                </span>
              </div>
              <div class="memory-content">{{ mem.content }}</div>
              <div class="memory-chars" v-if="mem.involved_characters?.length">
                涉及: {{ mem.involved_characters.join(', ') }}
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Emotion History -->
        <el-tab-pane label="📈 情感轨迹" name="emotions">
          <EmotionChart :character-id="character.id" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <div class="profile-actions">
      <el-button type="primary" @click="$emit('open-agent-editor')">📝 编辑 Agent 文件</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import EmotionChart from './EmotionChart.vue'
import client from '@/api/client'
import type { Character } from '@/api/types'

const props = defineProps<{ character: Character }>()
defineEmits<{ 'open-agent-editor': [] }>()

const activeTab = ref('actions')
const fullProfile = ref<any>(null)
const allActions = ref<any[]>([])
const allMemories = ref<any[]>([])
const actionsLoading = ref(false)
const memoriesLoading = ref(false)

const emotionLabels: Record<string, string> = {
  happiness: '😊 快乐', anger: '😡 愤怒', fear: '😨 恐惧',
  sadness: '😢 悲伤', trust: '🤝 信任', surprise: '😲 惊讶',
}

const actionIcons: Record<string, string> = {
  dialogue: '💬', thought: '💭', behavior: '⚡', reaction: '🔄',
}

function actionTypeLabel(t: string) {
  const m: Record<string, string> = { dialogue: '对话', thought: '内心', behavior: '行动', reaction: '反应' }
  return m[t] || t
}

function actionTagType(t: string): any {
  const m: Record<string, string> = { dialogue: '', thought: 'info', behavior: 'success', reaction: 'warning' }
  return m[t] || 'info'
}

const actionsByChapter = computed(() => {
  const groups: Record<number, any[]> = {}
  for (const a of allActions.value) {
    if (!groups[a.chapter_index]) groups[a.chapter_index] = []
    groups[a.chapter_index].push(a)
  }
  return groups
})

async function loadFullProfile() {
  try {
    const { data } = await client.get(`/characters/${props.character.id}/full-profile`)
    fullProfile.value = data
  } catch { /* ignore */ }
}

async function loadActions() {
  actionsLoading.value = true
  try {
    const { data } = await client.get(`/characters/${props.character.id}/actions-all`)
    allActions.value = data.actions || []
  } catch { /* ignore */ }
  actionsLoading.value = false
}

async function loadMemories() {
  memoriesLoading.value = true
  try {
    const { data } = await client.get(`/characters/${props.character.id}/memories`)
    allMemories.value = data.memories || []
  } catch { /* ignore */ }
  memoriesLoading.value = false
}

watch(() => props.character.id, () => {
  loadFullProfile()
  loadActions()
  loadMemories()
}, { immediate: true })

onMounted(() => {
  loadFullProfile()
  loadActions()
  loadMemories()
})
</script>

<style scoped lang="scss">
.character-profile { padding: var(--sp-sm); }

.profile-header {
  display: flex; align-items: center; gap: var(--sp-md); flex-wrap: wrap;
  h3 {
    font-family: var(--font-ui);
    font-size: var(--fs-lg);
    font-weight: 500;
    margin: 0;
    color: var(--text-primary);
  }
  .profile-stats {
    display: flex; gap: var(--sp-md);
    font-family: var(--font-data);
    font-size: var(--fs-xs);
    color: var(--text-muted);
    margin-left: auto;
  }
}

.profile-section {
  margin-bottom: var(--sp-lg);
  padding-bottom: var(--sp-lg);
  border-bottom: 1px solid var(--border-rule);

  .backstory-text {
    font-family: var(--font-ui);
    color: var(--text-primary);
    line-height: 2.0;
    font-size: var(--fs-md);
  }
}

.emotion-bars {
  display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-sm);
  .emotion-bar {
    display: flex; align-items: center; gap: var(--sp-sm);
    .emo-label {
      font-family: var(--font-ui);
      font-size: var(--fs-sm);
      min-width: 5rem;
      color: var(--text-secondary);
    }
    .el-progress { flex: 1; }
    .emo-value {
      font-family: var(--font-data);
      font-size: var(--fs-xs);
      color: var(--text-muted);
      min-width: 2.5rem;
      text-align: right;
    }
  }
}

.rel-table {
  display: flex;
  flex-direction: column;
}

.rel-row {
  display: flex; align-items: center; gap: var(--sp-sm); flex-wrap: wrap;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-ghost);
  font-size: var(--fs-sm);

  .rel-target {
    font-family: var(--font-ui);
    font-weight: 500;
    color: var(--accent-ember);
  }
  .rel-scores {
    font-family: var(--font-data);
    color: var(--text-secondary);
    font-size: var(--fs-xs);

    b { font-weight: 600; }
  }
  .rel-desc {
    color: var(--text-muted);
    font-size: var(--fs-xs);
    width: 100%;
    margin-top: var(--sp-2xs);
    font-family: var(--font-ui);
  }
}

.detail-tabs {
  background: transparent !important;
  border: none !important;
  :deep(.el-tabs__content) { padding: var(--sp-md) 0; }
}

.empty-hint {
  color: var(--text-muted);
  text-align: center;
  padding: var(--sp-2xl) 0;
  font-family: var(--font-ui);
}

// Action Timeline
.action-timeline { max-height: 500px; overflow-y: auto; }
.chapter-group { margin-bottom: var(--sp-md); }
.chapter-label {
  font-family: var(--font-ui);
  font-weight: 600;
  font-size: var(--fs-xs);
  color: var(--accent-ember);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: var(--sp-xs) 0;
  border-bottom: 1px solid var(--border-rule);
  margin-bottom: var(--sp-sm);
}

.action-item {
  display: flex; gap: var(--sp-sm); padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-ghost);
  .action-icon { font-size: 1.1rem; flex-shrink: 0; margin-top: 2px; }
  .action-body { flex: 1; min-width: 0; }
  .action-meta { display: flex; align-items: center; gap: var(--sp-sm); margin-bottom: var(--sp-2xs); }
  .scene-badge {
    font-family: var(--font-data);
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .target-badge {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    color: var(--accent-ember);
    font-weight: 500;
  }
  .action-content {
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    line-height: 1.85;
    color: var(--text-primary);
    white-space: pre-wrap;
    word-break: break-word;
  }
  &.type-thought .action-content { color: var(--text-secondary); font-style: italic; }
  &.type-dialogue .action-content { color: var(--text-primary); }
  &.type-behavior .action-content { color: var(--accent-jade); }
  &.type-reaction .action-content { color: var(--accent-ember); }
}

// Memory List
.memory-list { max-height: 500px; overflow-y: auto; }
.memory-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--border-ghost);
  .memory-meta {
    display: flex; align-items: center; gap: var(--sp-sm);
    font-family: var(--font-data);
    font-size: var(--fs-xs);
    color: var(--text-muted);
    margin-bottom: var(--sp-2xs);
  }
  .memory-content {
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    line-height: 1.85;
    color: var(--text-primary);
  }
  .memory-chars {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    color: var(--accent-aurora);
    margin-top: var(--sp-2xs);
  }
}

.profile-actions {
  display: flex; gap: var(--sp-md); margin-top: var(--sp-lg);
}
</style>
