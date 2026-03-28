<template>
  <div class="historian-chat">
    <div class="chat-header ledger-rule">
      <span class="chat-title">史官对话</span>
      <span class="chat-hint">与史官讨论剧情、角色、撰写章节</span>
      <el-button v-if="messages.length > 0" text size="small" @click="clearHistory" style="margin-left:auto">清空记录</el-button>
    </div>
    <div class="chat-messages" ref="msgContainer">
      <div v-if="messages.length === 0" class="chat-welcome">
        <p class="welcome-prose">你好，造物主。我是这个世界的史官，掌握所有角色的记忆与行动。</p>
        <p class="welcome-hint">你可以问我：</p>
        <div class="suggestions">
          <el-button v-for="s in suggestions" :key="s" size="small" plain @click="sendMessage(s)">{{ s }}</el-button>
        </div>
      </div>
      <div v-for="(msg, i) in messages" :key="i" :class="['chat-msg', msg.role]">
        <div class="msg-role">{{ msg.role === 'user' ? '造物主' : '史官' }}</div>
        <div class="msg-content" v-html="renderMarkdown(msg.content)"></div>
      </div>
      <div v-if="loading" class="chat-msg assistant">
        <div class="msg-role">史官</div>
        <div class="msg-content loading-dots">史官正在翻阅记录...</div>
      </div>
    </div>
    <div class="chat-input">
      <el-input
        v-model="input"
        placeholder="向史官提问或下达指令..."
        @keyup.enter="sendMessage()"
        :disabled="loading"
        size="large"
      >
        <template #append>
          <el-button :loading="loading" @click="sendMessage()" class="send-btn">发送</el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import client from '@/api/client'
import { useProgressStore } from '@/stores/progress'

const route = useRoute()
const progressStore = useProgressStore()
const input = ref('')
const loading = ref(false)
const msgContainer = ref<HTMLElement | null>(null)

interface ChatMessage { role: 'user' | 'assistant'; content: string }
const messages = ref<ChatMessage[]>([])

const suggestions = computed(() => {
  const chapter = progressStore.completed
  const dynamic: string[] = []
  if (chapter > 0) {
    dynamic.push(`分析第${chapter}章中角色的关系变化`)
    dynamic.push(`第${chapter}章有哪些伏笔被埋下了？`)
  }
  return [
    ...dynamic,
    '帮我梳理当前所有角色的关系变化',
    '分析目前的伏笔哪些还没回收',
    '建议下一章的剧情走向',
  ]
})

// --- localStorage 持久化 ---
function storageKey() {
  return `historian_chat_${route.params.novelId || 'default'}`
}

function saveToStorage() {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(messages.value))
  } catch { /* quota exceeded etc */ }
}

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(storageKey())
    if (raw) messages.value = JSON.parse(raw)
  } catch { /* ignore */ }
}

function clearHistory() {
  messages.value = []
  localStorage.removeItem(storageKey())
}

onMounted(() => {
  loadFromStorage()
  scrollToBottom()
})

// Save on every change
watch(messages, saveToStorage, { deep: true })

function renderMarkdown(text: string) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/### (.*?)(<br>|\n|$)/g, '<h4>$1</h4>')
    .replace(/## (.*?)(<br>|\n|$)/g, '<h3>$1</h3>')
    .replace(/\n/g, '<br>')
}

async function sendMessage(text?: string) {
  const msg = text || input.value.trim()
  if (!msg) return

  messages.value.push({ role: 'user', content: msg })
  input.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const novelId = route.params.novelId as string
    const { data } = await client.post('/ai/historian-chat', {
      message: msg,
      novel_id: novelId,
      history: messages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
    })
    messages.value.push({ role: 'assistant', content: data.reply || '...' })
  } catch {
    messages.value.push({ role: 'assistant', content: '史官暂时无法回应，请稍后再试。' })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  })
}
</script>

<style scoped lang="scss">
.historian-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 500px;
}

.chat-header {
  display: flex;
  align-items: baseline;
  gap: var(--sp-sm);

  .chat-title {
    font-family: var(--font-ui);
    font-size: var(--fs-lg);
    font-weight: 400;
    color: var(--text-primary);
  }
  .chat-hint {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-md) 0;
  min-height: 300px;
}

.chat-welcome {
  padding: var(--sp-2xl) 0;
  color: var(--text-muted);

  .welcome-prose {
    font-family: var(--font-ui);
    font-size: var(--fs-md);
    line-height: 1.85;
    color: var(--text-secondary);
    margin: 0 0 var(--sp-sm) 0;
  }
  .welcome-hint {
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
    color: var(--text-muted);
    margin: 0 0 var(--sp-md) 0;
  }
  .suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--sp-sm);
  }
}

.chat-msg {
  padding: var(--sp-md) 0;
  border-bottom: 1px solid var(--border-ghost);

  .msg-role {
    font-family: var(--font-ui);
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: var(--sp-sm);
  }

  .msg-content {
    font-size: var(--fs-base);
    line-height: 1.5;
    color: var(--text-primary);

    :deep(strong) { color: var(--accent-ember); }
    :deep(h3) {
      font-family: var(--font-ui);
      font-size: var(--fs-lg);
      margin: var(--sp-md) 0 var(--sp-sm);
      color: var(--text-primary);
    }
    :deep(h4) {
      font-family: var(--font-ui);
      font-size: var(--fs-base);
      font-weight: 600;
      margin: var(--sp-sm) 0 var(--sp-xs);
      color: var(--text-secondary);
    }
  }

  &.assistant .msg-content {
    font-family: var(--font-ui);
    font-size: var(--fs-md);
    line-height: 1.85;
  }

  &.user .msg-content {
    font-family: var(--font-ui);
    font-size: var(--fs-base);
  }

  &.user .msg-role {
    color: var(--accent-ember);
  }

  .loading-dots {
    color: var(--text-muted);
    font-style: italic;
    animation: pulse 1.5s infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.chat-input {
  padding-top: var(--sp-md);
  border-top: 1px solid var(--border-rule);

  .send-btn {
    background: var(--accent-ember) !important;
    color: var(--text-inverse) !important;
    border-color: var(--accent-ember) !important;
    border-radius: 6px !important;
    font-family: var(--font-ui);
    font-weight: 600;
  }
}
</style>
