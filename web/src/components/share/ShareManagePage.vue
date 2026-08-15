<template>
  <div class="shares-page">
    <header class="page-head">
      <div>
        <h1>分享管理</h1>
        <p class="page-sub">把成书生成公开链接 — 匿名读者试读，注册即可阅读全文</p>
      </div>
      <button class="btn-primary" @click="openCreate">新建分享</button>
    </header>

    <div v-if="loading" class="state-hint">加载中…</div>
    <div v-else-if="shares.length === 0" class="state-hint">
      还没有分享。点击右上角「新建分享」，把你的小说分享给读者。
    </div>

    <div v-else class="share-list">
      <div v-for="s in shares" :key="s.share_id" class="share-card">
        <div class="share-main">
          <div class="share-title-row">
            <h3>{{ s.title || s.novel_id }}</h3>
            <span class="badge" :class="s.status === 'active' ? 'badge--on' : 'badge--off'">
              {{ s.status === 'active' ? '分享中' : '已关闭' }}
            </span>
          </div>
          <a class="share-url" :href="s.share_url" target="_blank">{{ s.share_url }}</a>
          <div class="share-stats-row">
            <span>浏览 <b>{{ s.view_count }}</b></span>
            <span>阅读 <b>{{ s.read_count }}</b></span>
            <span>注册转化 <b>{{ s.register_count }}</b></span>
            <span class="trial-info">
              试读：{{ trialLabel(s.trial_mode, s.trial_value) }}
            </span>
          </div>
        </div>

        <div class="share-actions">
          <button class="btn-sm" @click="copyLink(s.share_url)">复制链接</button>
          <button class="btn-sm" @click="openEdit(s)">试读设置</button>
          <button class="btn-sm" @click="openStats(s)">数据</button>
          <button
            v-if="s.status === 'active'"
            class="btn-sm btn-sm--danger"
            @click="toggleStatus(s)"
          >
            关闭分享
          </button>
          <button v-else class="btn-sm" @click="toggleStatus(s)">重新开启</button>
        </div>
      </div>
    </div>

    <!-- Create dialog -->
    <div v-if="createOpen" class="modal-scrim" @click.self="createOpen = false">
      <div class="modal-card">
        <h3>新建分享</h3>
        <label class="field-label">选择小说</label>
        <select v-model="createForm.novel_id" class="field-input">
          <option value="" disabled>请选择…</option>
          <option v-for="n in novels" :key="n.novel_id" :value="n.novel_id">
            {{ n.title }}（{{ n.chapters_completed || 0 }} 章）
          </option>
        </select>

        <label class="field-label">试读策略</label>
        <select v-model="createForm.trial_mode" class="field-input">
          <option value="first_n_chapters">前 N 章免费试读</option>
          <option value="word_count">前 N 字免费试读</option>
          <option value="ratio">按全书比例试读（%）</option>
        </select>
        <input
          v-model.number="createForm.trial_value"
          type="number"
          min="0"
          class="field-input"
          :placeholder="trialValueHint"
        />
        <p class="field-hint">{{ trialValueHint }}</p>

        <div v-if="createError" class="form-error">{{ createError }}</div>

        <div class="modal-actions">
          <button class="btn-ghost" @click="createOpen = false">取消</button>
          <button class="btn-primary" :disabled="creating" @click="doCreate">
            {{ creating ? '创建中…' : '创建分享' }}
          </button>
        </div>

        <div v-if="createdUrl" class="created-box">
          <p>分享链接已生成：</p>
          <code>{{ createdUrl }}</code>
          <button class="btn-sm" @click="copyLink(createdUrl)">复制</button>
        </div>
      </div>
    </div>

    <!-- Edit trial dialog -->
    <div v-if="editOpen && editTarget" class="modal-scrim" @click.self="editOpen = false">
      <div class="modal-card">
        <h3>试读设置 · {{ editTarget.title || editTarget.novel_id }}</h3>
        <label class="field-label">试读策略</label>
        <select v-model="editForm.trial_mode" class="field-input">
          <option value="first_n_chapters">前 N 章免费试读</option>
          <option value="word_count">前 N 字免费试读</option>
          <option value="ratio">按全书比例试读（%）</option>
        </select>
        <input
          v-model.number="editForm.trial_value"
          type="number"
          min="0"
          class="field-input"
        />
        <p class="field-hint">修改立即生效。设为 0 表示不提供试读。</p>

        <div class="modal-actions">
          <button class="btn-ghost" @click="editOpen = false">取消</button>
          <button class="btn-primary" @click="doEdit">保存</button>
        </div>
      </div>
    </div>

    <!-- Stats dialog -->
    <div v-if="statsOpen && statsTarget" class="modal-scrim" @click.self="statsOpen = false">
      <div class="modal-card modal-card--wide">
        <h3>阅读数据 · {{ statsTarget.title || statsTarget.novel_id }}</h3>
        <div class="stats-totals">
          <div class="stat-box">
            <span class="stat-num">{{ statsData?.view_count ?? '—' }}</span>
            <span class="stat-label">总浏览 (PV)</span>
          </div>
          <div class="stat-box">
            <span class="stat-num">{{ statsData?.read_count ?? '—' }}</span>
            <span class="stat-label">章节阅读</span>
          </div>
          <div class="stat-box">
            <span class="stat-num">{{ statsData?.register_count ?? '—' }}</span>
            <span class="stat-label">注册转化</span>
          </div>
        </div>
        <table v-if="statsData?.daily?.length" class="stats-table">
          <thead>
            <tr><th>日期</th><th>浏览</th><th>阅读</th><th>访客(UV)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in statsData.daily" :key="d.stat_date">
              <td>{{ d.stat_date }}</td>
              <td>{{ d.views }}</td>
              <td>{{ d.reads }}</td>
              <td>{{ d.visitors }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="state-hint">近 30 天暂无访问数据。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import client from '@/api/client'
import {
  listMyShares,
  createShare,
  patchShare,
  getShareStats,
  type AuthorShare,
} from '@/api/share'

interface NovelLite {
  novel_id: string
  title: string
  chapters_completed?: number
}

const loading = ref(true)
const shares = ref<AuthorShare[]>([])
const novels = ref<NovelLite[]>([])

const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')
const createdUrl = ref('')
const createForm = reactive({
  novel_id: '',
  trial_mode: 'first_n_chapters',
  trial_value: 3,
})

const editOpen = ref(false)
const editTarget = ref<AuthorShare | null>(null)
const editForm = reactive({ trial_mode: 'first_n_chapters', trial_value: 3 })

const statsOpen = ref(false)
const statsTarget = ref<AuthorShare | null>(null)
const statsData = ref<any>(null)

const trialValueHint = computed(() => {
  switch (createForm.trial_mode) {
    case 'word_count':
      return '输入试读字数，如 5000'
    case 'ratio':
      return '输入百分比（0-100），如 10 表示前 10%'
    default:
      return '输入试读章节数，如 3'
  }
})

function trialLabel(mode: string, value: number): string {
  switch (mode) {
    case 'word_count':
      return `前 ${value} 字`
    case 'ratio':
      return `前 ${value}%`
    default:
      return `前 ${value} 章`
  }
}

async function load() {
  loading.value = true
  try {
    const [{ data }, novelsResp] = await Promise.all([
      listMyShares(),
      client.get('/novels'),
    ])
    shares.value = data.shares || []
    novels.value = novelsResp.data.novels || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createError.value = ''
  createdUrl.value = ''
  createForm.novel_id = ''
  createForm.trial_mode = 'first_n_chapters'
  createForm.trial_value = 3
  createOpen.value = true
}

async function doCreate() {
  if (!createForm.novel_id) {
    createError.value = '请选择要分享的小说'
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const { data } = await createShare({
      novel_id: createForm.novel_id,
      trial_mode: createForm.trial_mode,
      trial_value: createForm.trial_value,
    })
    createdUrl.value = data.share_url
    await load()
  } catch (e: any) {
    createError.value = e.response?.data?.detail || '创建失败'
  } finally {
    creating.value = false
  }
}

function openEdit(s: AuthorShare) {
  editTarget.value = s
  editForm.trial_mode = s.trial_mode
  editForm.trial_value = s.trial_value
  editOpen.value = true
}

async function doEdit() {
  if (!editTarget.value) return
  await patchShare(editTarget.value.share_id, {
    trial_mode: editForm.trial_mode,
    trial_value: editForm.trial_value,
  })
  editOpen.value = false
  await load()
}

async function toggleStatus(s: AuthorShare) {
  const next = s.status === 'active' ? 'disabled' : 'active'
  await patchShare(s.share_id, { status: next })
  await load()
}

async function openStats(s: AuthorShare) {
  statsTarget.value = s
  statsData.value = null
  statsOpen.value = true
  const { data } = await getShareStats(s.share_id)
  statsData.value = data
}

async function copyLink(url: string) {
  try {
    await navigator.clipboard.writeText(url)
  } catch {
    // fallback for non-secure contexts
    const el = document.createElement('textarea')
    el.value = url
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    el.remove()
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.shares-page {
  max-width: 900px;
  margin: 0 auto;
  padding: var(--sp-xl) var(--sp-md);
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);

  h1 {
    margin: 0;
    font-size: var(--fs-lg);
  }

  .page-sub {
    color: var(--text-secondary);
    font-size: var(--fs-sm);
    margin: var(--sp-xs) 0 0;
  }
}

.btn-primary {
  background: var(--accent-ember);
  border: none;
  color: #fff;
  padding: 9px 18px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--fs-sm);
  flex-shrink: 0;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.state-hint {
  color: var(--text-muted);
  text-align: center;
  padding: var(--sp-2xl);
  font-size: var(--fs-sm);
}

.share-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-md);
}

.share-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  padding: var(--sp-md);
  display: flex;
  flex-direction: column;
  gap: var(--sp-md);
  box-shadow: var(--shadow-sm);
}

.share-title-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);

  h3 {
    margin: 0;
    font-size: var(--fs-base);
  }
}

.badge {
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: var(--radius-badge);

  &--on {
    color: var(--accent-jade);
    background: rgba(5, 150, 105, 0.1);
  }

  &--off {
    color: var(--text-muted);
    background: var(--bg-elevated);
  }
}

.share-url {
  color: var(--accent-blue);
  font-size: var(--fs-sm);
  word-break: break-all;
}

.share-stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-md);
  color: var(--text-secondary);
  font-size: var(--fs-sm);

  b {
    color: var(--text-primary);
    font-family: var(--font-data);
  }

  .trial-info {
    color: var(--text-muted);
  }
}

.share-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-sm);
}

.btn-sm {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--fs-xs);
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;

  &:hover {
    border-color: var(--border-active);
    color: var(--accent-ember);
  }

  &--danger:hover {
    border-color: var(--accent-cinnabar);
    color: var(--accent-cinnabar);
  }
}

// ── Modals ───────────────────────────────────────────
.modal-scrim {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-md);
}

.modal-card {
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-deep);
  padding: var(--sp-xl);
  max-width: 420px;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;

  &--wide {
    max-width: 560px;
  }

  h3 {
    margin: 0 0 var(--sp-md);
    font-size: var(--fs-base);
  }
}

.field-label {
  display: block;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin: var(--sp-sm) 0 var(--sp-xs);
}

.field-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-void);
  color: var(--text-primary);
  font-size: var(--fs-sm);
  margin-bottom: var(--sp-xs);
  box-sizing: border-box;
}

.field-hint {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  margin: 0 0 var(--sp-sm);
}

.form-error {
  color: var(--accent-cinnabar);
  font-size: var(--fs-sm);
  margin-bottom: var(--sp-sm);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-sm);
  margin-top: var(--sp-md);
}

.btn-ghost {
  border: 1px solid var(--border-default);
  background: none;
  color: var(--text-secondary);
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--fs-sm);
}

.created-box {
  margin-top: var(--sp-md);
  padding: var(--sp-md);
  background: var(--accent-ember-dim);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);

  code {
    display: block;
    word-break: break-all;
    margin: var(--sp-xs) 0;
    color: var(--accent-ember);
  }
}

.stats-totals {
  display: flex;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-md);
}

.stat-box {
  flex: 1;
  text-align: center;
  padding: var(--sp-md);
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);

  .stat-num {
    font-family: var(--font-data);
    font-size: var(--fs-lg);
    color: var(--accent-ember);
  }

  .stat-label {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
}

.stats-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-sm);

  th, td {
    text-align: left;
    padding: 6px 8px;
    border-bottom: 1px solid var(--border-muted);
  }

  th {
    color: var(--text-muted);
    font-weight: 500;
  }
}
</style>
