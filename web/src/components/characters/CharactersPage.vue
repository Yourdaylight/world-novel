<template>
  <div class="characters-page" v-loading="characterStore.loading">
    <el-row :gutter="20">
      <el-col :span="14">
        <div class="ledger-zone">
          <span class="section-label">关系图谱</span>
          <RelationshipGraph @node-click="onGraphNodeClick" />
        </div>
      </el-col>
      <el-col :span="10">
        <div class="ledger-zone">
          <span class="section-label">角色列表</span>
          <div class="character-list">
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
          <EmptyState v-if="!characterStore.characters.length" message="暂无角色数据" />
        </div>
      </el-col>
    </el-row>

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
.ledger-zone {
  padding-bottom: var(--sp-lg);
}

.character-list {
  display: flex;
  flex-direction: column;
  max-height: 500px;
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
</style>
