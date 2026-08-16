<template>
  <div class="share-page page-container">
    <header class="page-header">
      <h1 class="page-title">分享管理</h1>
      <span class="page-subtitle">公开链接 · 试读策略 · 阅读数据</span>
    </header>

    <div class="page-content">
      <section class="card share-card">
        <h3 class="section-label">公开分享</h3>

        <div v-if="!share" class="no-share">
          <p class="hint-text">
            生成公开阅读链接后，任何人可通过链接阅读封面、简介、目录与试读章节；
            注册平台账号（邀请码）后即可阅读全书。
          </p>
          <div class="trial-row">
            <span class="trial-label">试读策略</span>
            <select v-model="form.trial_mode" class="text-input select">
              <option value="first_n_chapters">按章节数</option>
              <option value="word_count">按字数</option>
              <option value="ratio">按比例</option>
              <option value="all">全本开放</option>
            </select>
            <input
              v-if="form.trial_mode !== 'all'"
              v-model.number="form.trial_value"
              type="number"
              min="0"
              class="text-input num"
            />
            <span class="trial-unit">{{ unitText }}</span>
          </div>
          <button class="btn-primary" :disabled="creating" @click="create">
            {{ creating ? '生成中…' : '生成分享链接' }}
          </button>
        </div>

        <div v-else class="share-detail">
          <div class="share-status-row">
            <span class="status-badge" :class="share.status === 'active' ? 'on' : 'off'">
              {{ share.status === 'active' ? '分享中' : '已关闭' }}
            </span>
            <span class="hint-text inline">创建于 {{ share.created_at }}</span>
          </div>

          <label class="url-label">公开阅读地址</label>
          <div class="url-row">
            <input class="text-input url-input" :value="shareUrl" readonly />
            <button class="btn-secondary" @click="copyUrl">复制链接</button>
            <button class="btn-secondary" @click="openReader">打开阅读页</button>
          </div>

          <div class="trial-row">
            <span class="trial-label">试读策略</span>
            <select v-model="form.trial_mode" class="text-input select" @change="saveTrial">
              <option value="first_n_chapters">按章节数</option>
              <option value="word_count">按字数</option>
              <option value="ratio">按比例</option>
              <option value="all">全本开放</option>
            </select>
            <input
              v-if="form.trial_mode !== 'all'"
              v-model.number="form.trial_value"
              type="number"
              min="0"
              class="text-input num"
              @change="saveTrial"
            />
            <span class="trial-unit">{{ unitText }}</span>
            <span class="hint-text inline" v-if="form.trial_mode === 'first_n_chapters' && form.trial_value === 0">
              0 = 完全锁定，注册后可读
            </span>
          </div>

          <div class="stat-row">
            <div class="stat-cell">
              <span class="stat-num font-data">{{ share.view_count }}</span>
              <span class="stat-label">访问 PV</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num font-data">{{ share.read_count }}</span>
              <span class="stat-label">章节阅读</span>
            </div>
          </div>

          <div class="danger-row">
            <button v-if="share.status === 'active'" class="btn-danger-ghost" @click="toggleStatus('disabled')">
              关闭分享（立即失效）
            </button>
            <button v-else class="btn-secondary" @click="toggleStatus('active')">
              重新开启分享
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createShare, listMyShares, patchShare, type ShareLink } from '@/api/share'

const route = useRoute()
const novelId = () => route.params.novelId as string

const share = ref<ShareLink | null>(null)
const creating = ref(false)
const form = ref({ trial_mode: 'first_n_chapters', trial_value: 3 })

const shareUrl = computed(() => `${window.location.origin}/read/${share.value?.id || ''}`)

const unitText = computed(() => {
  switch (form.value.trial_mode) {
    case 'word_count': return '字'
    case 'ratio': return '%'
    case 'all': return ''
    default: return '章'
  }
})

async function load() {
  try {
    const all = await listMyShares()
    share.value = all.find((s) => s.novel_id === novelId()) || null
    if (share.value) {
      form.value = {
        trial_mode: share.value.trial_mode,
        trial_value: share.value.trial_value,
      }
    }
  } catch { /* ignore */ }
}

async function create() {
  creating.value = true
  try {
    const res = await createShare({
      novel_id: novelId(),
      trial_mode: form.value.trial_mode,
      trial_value: form.value.trial_value,
    })
    ElMessage.success(res.created ? '分享链接已生成' : '已有生效中的分享')
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.error || '生成失败')
  } finally {
    creating.value = false
  }
}

async function saveTrial() {
  if (!share.value) return
  try {
    await patchShare(share.value.id, {
      trial_mode: form.value.trial_mode,
      trial_value: Number(form.value.trial_value) || 0,
    })
    ElMessage.success('试读策略已更新')
    await load()
  } catch {
    ElMessage.error('保存失败')
  }
}

async function toggleStatus(status: string) {
  if (!share.value) return
  try {
    await patchShare(share.value.id, { status })
    ElMessage.success(status === 'disabled' ? '分享已关闭' : '分享已重新开启')
    await load()
  } catch {
    ElMessage.error('操作失败')
  }
}

function copyUrl() {
  navigator.clipboard.writeText(shareUrl.value)
    .then(() => ElMessage.success('链接已复制'))
    .catch(() => ElMessage.warning('复制失败，请手动选择复制'))
}

function openReader() {
  window.open(shareUrl.value, '_blank', 'noopener')
}

onMounted(load)
</script>

<style scoped lang="scss">
.page-container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 var(--sp-lg);
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
}

.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

.share-card { max-width: 680px; }

.hint-text {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  line-height: 1.7;

  &.inline { margin: 0; }
}

.trial-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin: var(--sp-md) 0;
  flex-wrap: wrap;
}

.trial-label {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.trial-unit {
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

.select { width: 130px; }
.num { width: 90px; }

.text-input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-void);
  color: var(--text-primary);
  font-size: var(--fs-sm);

  &:focus { outline: none; border-color: var(--accent-ember); }
}

.btn-primary,
.btn-secondary {
  height: 34px;
  padding: 0 16px;
  border-radius: var(--radius-md);
  font-size: var(--fs-sm);
  font-weight: 550;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-primary {
  background: var(--accent-ember);
  color: var(--text-inverse);
  &:hover { background: #b45309; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.btn-secondary {
  background: var(--bg-elevated);
  border-color: var(--border-default);
  color: var(--text-secondary);
}

.share-status-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-md);
}

.status-badge {
  font-size: var(--fs-xs);
  padding: 2px 10px;
  border-radius: 6px;

  &.on { background: rgba(5, 150, 105, 0.1); color: var(--accent-jade); }
  &.off { background: rgba(220, 38, 38, 0.1); color: var(--accent-cinnabar); }
}

.url-label {
  display: block;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.url-row {
  display: flex;
  gap: var(--sp-xs);
  margin-bottom: var(--sp-md);

  .url-input { flex: 1; font-family: var(--font-data); font-size: var(--fs-xs); }
}

.stat-row {
  display: flex;
  gap: var(--sp-md);
  margin: var(--sp-md) 0;
}

.stat-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 96px;
  padding: var(--sp-sm) var(--sp-lg);
  border: 1px solid var(--border-muted);
  border-radius: var(--radius-md);
}

.stat-num { font-size: var(--fs-lg); font-weight: 650; color: var(--text-primary); }
.stat-label { font-size: var(--fs-xs); color: var(--text-muted); margin-top: 2px; }

.danger-row { margin-top: var(--sp-md); }

.btn-danger-ghost {
  height: 32px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  background: transparent;
  border: 1px solid rgba(220, 38, 38, 0.4);
  color: var(--accent-cinnabar);
  font-size: var(--fs-sm);
  cursor: pointer;

  &:hover { background: rgba(220, 38, 38, 0.06); }
}
</style>
