<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="`Agent 文件 — ${characterName}`"
    size="70%"
    direction="rtl"
    :destroy-on-close="true"
  >
    <div class="agent-editor" v-loading="loading">
      <el-row :gutter="20" style="height: 100%">
        <!-- agent.md (read-only) -->
        <el-col :span="12">
          <div class="editor-panel">
            <div class="panel-title">
              <span class="panel-label">📄 agent.md</span>
              <el-tag size="small" type="info">只读</el-tag>
            </div>
            <div class="md-content" v-html="renderMarkdown(agentMd)"></div>
          </div>
        </el-col>

        <!-- soul.md (editable) -->
        <el-col :span="12">
          <div class="editor-panel">
            <div class="panel-title">
              <span class="panel-label">✨ soul.md</span>
              <el-button type="primary" size="small" @click="save" :loading="agentStore.saving">
                💾 保存
              </el-button>
            </div>
            <MdEditor
              v-model="soulContent"
              language="zh-CN"
              :theme="'dark'"
              :style="{ height: '500px' }"
              :preview="false"
            />
          </div>
        </el-col>
      </el-row>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MdEditor } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { useAgentStore } from '@/stores/agents'
import { escapeHtml } from '@/utils/escapeHtml'

const props = defineProps<{
  visible: boolean
  characterId: string
  characterName: string
}>()

defineEmits<{ 'update:visible': [value: boolean] }>()

const agentStore = useAgentStore()
const agentMd = ref('')
const soulContent = ref('')
const loading = ref(false)

watch(() => props.visible, async (val) => {
  if (val && props.characterId) {
    loading.value = true
    try {
      const files = await agentStore.loadFiles(props.characterId)
      agentMd.value = files.agent_md
      soulContent.value = files.soul_md
    } finally {
      loading.value = false
    }
  }
})

async function save() {
  const res = await agentStore.saveSoul(props.characterId, soulContent.value)
  if (res.ok) {
    ElMessage.success('soul.md 已保存并同步到数据库')
  } else {
    ElMessage.error('保存失败: ' + (res.error || '未知错误'))
  }
}

function renderMarkdown(text: string): string {
  // Simple markdown rendering for read-only display
  return escapeHtml(text)
    .replace(/^### (.+)$/gm, '<h3 style="color:var(--accent-aurora);margin:1rem 0 0.5rem">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="color:var(--accent-ember);margin:1rem 0 0.5rem">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="color:var(--text-primary);margin:1rem 0 0.5rem">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code style="background:var(--bg-elevated);padding:0.15em 0.3em;color:var(--accent-ember)">$1</code>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:1rem;color:var(--text-secondary)">$1</li>')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped lang="scss">
.agent-editor {
  height: calc(100vh - 120px);
}
.editor-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-md);
  padding-bottom: var(--sp-sm);
  border-bottom: 1px solid var(--border-rule);

  .panel-label {
    font-family: var(--font-ui);
    font-weight: 600;
    font-size: var(--fs-sm);
    color: var(--text-primary);
  }
}
.md-content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-surface);
  padding: var(--sp-md);
  border: 1px solid var(--border-rule);
  border-radius: 6px;
  line-height: 1.85;
  font-family: var(--font-ui);
  color: var(--text-secondary);
}
</style>
