<template>
  <div class="characters-page" v-loading="characterStore.loading">
    <header class="page-header">
      <h1 class="page-title">角色</h1>
    </header>

    <div class="cards-grid">
      <RelationshipGraph @node-click="onGraphNodeClick" />

      <div class="card character-list-card">
        <div class="card-header">
          <span class="card-icon">☺</span>
          <span class="card-title">角色列表</span>
        </div>
        <div class="card-body">
          <div v-if="characterStore.characters.length" class="character-list">
            <div
              v-for="char in characterStore.characters"
              :key="char.id"
              class="character-row"
              @click="openCharacter(char)"
            >
              <div class="char-header">
                <span class="char-name">{{ char.name }}</span>
                <el-tag size="small">{{ formatRole(char.role) }}</el-tag>
              </div>
              <p class="char-backstory">{{ truncate(char.backstory, 120) }}</p>
            </div>
          </div>
          <EmptyState v-else message="暂无角色数据" class="compact-empty" />
        </div>
      </div>
    </div>

    <!-- Character Profile Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="selectedChar?.name || '角色详情'"
      size="60%"
      direction="rtl"
    >
      <CharacterProfile
        v-if="selectedChar"
        :character="selectedChar"
        @open-agent-editor="openAgentEditor"
      />
    </el-drawer>

    <!-- Agent File Editor Drawer -->
    <AgentFileEditor
      v-model:visible="agentEditorVisible"
      :character-id="selectedChar?.id || ''"
      :character-name="selectedChar?.name || ''"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useCharacterStore } from '@/stores/characters'
import EmptyState from '@/components/common/EmptyState.vue'
import RelationshipGraph from './RelationshipGraph.vue'
import CharacterProfile from './CharacterProfile.vue'
import AgentFileEditor from './AgentFileEditor.vue'
import { truncate, formatRole } from '@/utils/formatters'
import type { Character } from '@/api/types'

const characterStore = useCharacterStore()
const drawerVisible = ref(false)
const agentEditorVisible = ref(false)
const selectedChar = ref<Character | null>(null)

onMounted(() => {
  characterStore.loadCharacters()
})

function openCharacter(char: Character) {
  selectedChar.value = char
  drawerVisible.value = true
}

function openAgentEditor() {
  agentEditorVisible.value = true
}

function onGraphNodeClick(characterId: string) {
  const char = characterStore.characters.find(c => c.id === characterId)
  if (char) {
    openCharacter(char)
  }
}
</script>

<style scoped lang="scss">
.characters-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--sp-xl) var(--sp-lg);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
  flex-wrap: wrap;
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-2xl);
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  margin: 0;
}

.cards-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: var(--sp-lg);
  align-items: stretch;
}

.character-list-card {
  display: flex;
  flex-direction: column;
  min-height: 400px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-md);
  border-bottom: 1px solid var(--border-muted);
}

.card-icon {
  font-size: 1.1rem;
  opacity: 0.7;
}

.card-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.card-body {
  padding: var(--sp-md);
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.character-list {
  display: flex;
  flex-direction: column;
  max-height: 600px;
  overflow-y: auto;
}

.character-row {
  padding: var(--sp-sm) 0;
  border-bottom: 1px solid var(--border-rule);
  cursor: pointer;

  &:hover {
    background: var(--accent-ember-dim);
  }

  &:last-child {
    border-bottom: none;
  }
}

.char-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-xs);
}

.char-name {
  font-family: var(--font-ui);
  font-weight: 500;
  font-size: var(--fs-md);
  color: var(--text-primary);
}

.char-backstory {
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  line-height: 1.5;
}

:deep(.empty-state.compact-empty) {
  padding: var(--sp-lg) var(--sp-md);
}

@media (max-width: 768px) {
  .characters-page {
    padding: var(--sp-lg) var(--sp-md);
  }

  .cards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
