<template>
  <div class="share-page">
    <header class="page-head">
      <h1 class="page-title">分享与公开阅读</h1>
      <p class="page-sub">
        生成不可枚举的公开链接。匿名读者仅能试读，使用邀请码注册后即可阅读全书，阅读进度自动同步。
      </p>
    </header>

    <div v-if="loading" class="muted">加载中…</div>

    <template v-else>
      <!-- No share yet -->
      <section v-if="!share" class="card create-card">
        <h2>创建分享链接</h2>
        <div class="trial-row">
          <label>试读策略</label>
          <select v-model="trialMode" class="ctrl">
            <option value="first_n_chapters">按章节数</option>
            <option value="word_count">按字数</option>
            <option value="ratio">按比例</option>
          </select>
          <input v-model.number="trialValue" type="number" min="0" class="ctrl small" />
          <span class="unit">{{ trialUnit }}</span>
        </div>
        <p class="hint">{{ trialHint }}</p>
        <button class="primary-btn" :disabled="creating" @click="create">
          {{ creating ? '生成中…' : '生成公开链接' }}
        </button>
        <p v-if="error" class="err">{{ error }}</p>
      </section>

      <!-- Existing share -->
      <section v-else class="card">
        <div class="share-head">
          <h2>{{ share.title }}</h2>
          <span class="status-dot" :class="share.status">{{ statusText(share.status) }}</span>
        </div>

        <div class="link-row" v-if="share.status === 'active'">
          <input class="link-input font-data" readonly :value="publicUrl" @focus="($event.target as HTMLInputElement).select()" />
          <button class="ghost-btn" @click="copyLink">{{ copied ? '已复制' : '复制链接' }}</button>
          <a class="ghost-btn" :href="`/read/${share.id}`" target="_blank">预览</a>
        </div>

        <div class="stats-row">
          <div class="stat"><span class="stat-num font-data">{{ share.view_count }}</span><span class="stat-label">浏览</span></div>
          <div class="stat"><span class="stat-num font-data">{{ share.read_count }}</span><span class="stat-label">章节阅读</span></div>
          <div class="stat"><span class="stat-num font-data">{{ share.chapters_total }}</span><span class="stat-label">总章节</span></div>
        </div>

        <div class="trial-row">
          <label>试读策略</label>
          <select v-model="trialMode" class="ctrl">
            <option value="first_n_chapters">按章节数</option>
            <option value="word_count">按字数</option>
            <option value="ratio">按比例</option>
          </select>
          <input v-model.number="trialValue" type="number" min="0" class="ctrl small" />
          <span class="unit">{{ trialUnit }}</span>
          <button class="ghost-btn" @click="saveTrial">保存策略</button>
        </div>
        <p class="hint">{{ trialHint }}（改动对新老读者即时生效）</p>

        <div class="action-row">
          <button v-if="share.status === 'active'" class="danger-btn" @click="toggle(false)">关闭分享</button>
          <button v-else class="primary-btn" @click="toggle(true)">重新开启</button>
          <router-link class="text-link" :to="{ name: 'publish', params: { novelId } }">前往成书发布 →</router-link>
        </div>
        <p v-if="share.status === 'disabled'" class="warn-text">
          分享已关闭，所有公开阅读接口立即返回 404；重新开启后原链接继续有效。
        </p>
        <p v-if="msg" class="ok-text">{{ msg }}</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  createShare,
  listMyShares,
  updateShare,
  type OwnerShare,
  type TrialMode,
} from '@/api/share'
import axios from 'axios'

const route = useRoute()
const novelId = String(route.params.novelId || '')

const loading = ref(true)
const creating = ref(false)
const share = ref<OwnerShare | null>(null)
const trialMode = ref<TrialMode>('first_n_chapters')
const trialValue = ref<number>(3)
const error = ref('')
const msg = ref('')
const copied = ref(false)

const publicUrl = computed(() => `${window.location.origin}/read/${share.value?.id || ''}`)
const trialUnit = computed(() =>
  trialMode.value === 'first_n_chapters' ? '章' : trialMode.value === 'word_count' ? '字' : '%',
)
const trialHint = computed(() => {
  if (trialMode.value === 'first_n_chapters') return `匿名读者可读前 ${trialValue.value} 章，之后需注册`
  if (trialMode.value === 'word_count') return `匿名读者累计可读约 ${trialValue.value} 字`
  return `匿名读者可读全书 ${trialValue.value}% 的章节`
})

function applyShare(s: OwnerShare) {
  share.value = s
  trialMode.value = s.trial_mode
  trialValue.value = s.trial_value
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const mine = await listMyShares()
    const found = mine.find(s => s.novel_id === novelId) || null
    if (found) applyShare(found)
  } catch (e) {
    error.value = '加载分享信息失败'
  } finally {
    loading.value = false
  }
}

async function create() {
  creating.value = true
  error.value = ''
  try {
    const res = await createShare(novelId, {
      trial_mode: trialMode.value,
      trial_value: Number(trialValue.value) || 0,
    })
    applyShare(res.share)
  } catch (e: any) {
    error.value = axios.isAxiosError(e) && e.response?.status === 404
      ? '该小说尚无成文章节，无法分享'
      : '创建失败，请确认已登录'
  } finally {
    creating.value = false
  }
}

async function saveTrial() {
  if (!share.value) return
  msg.value = ''
  try {
    const res = await updateShare(share.value.id, {
      trial_mode: trialMode.value,
      trial_value: Number(trialValue.value) || 0,
    })
    applyShare(res.share)
    msg.value = '试读策略已更新'
  } catch {
    error.value = '保存失败'
  }
}

async function toggle(active: boolean) {
  if (!share.value) return
  const res = await updateShare(share.value.id, { status: active ? 'active' : 'disabled' })
  applyShare(res.share)
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(publicUrl.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    /* clipboard unavailable */
  }
}

function statusText(s: string) {
  return s === 'active' ? '分享中' : '已关闭'
}

watch(() => route.params.novelId, () => load())
onMounted(load)
</script>

<style scoped lang="scss">
.share-page { max-width: 760px; display: flex; flex-direction: column; gap: var(--sp-lg); }
.page-title { font-family: var(--font-display); font-size: var(--fs-xl); font-weight: 400; margin: 0 0 var(--sp-xs); }
.page-sub { color: var(--text-secondary); font-size: var(--fs-sm); margin: 0; line-height: 1.7; }
.card { background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); padding: var(--sp-lg); box-shadow: var(--shadow-sm); }
.share-head { display: flex; align-items: center; gap: var(--sp-sm); margin-bottom: var(--sp-md); h2 { font-size: var(--fs-md); margin: 0; } }
.muted, .hint { color: var(--text-muted); font-size: var(--fs-xs); }
.hint { margin: var(--sp-xs) 0 var(--sp-md); }
.err { color: var(--accent-cinnabar); font-size: var(--fs-sm); }
.warn-text { color: #b45309; font-size: var(--fs-sm); }
.ok-text { color: var(--accent-jade); font-size: var(--fs-sm); }

.link-row { display: flex; gap: var(--sp-sm); margin-bottom: var(--sp-lg); }
.link-input { flex: 1; padding: 9px 12px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); background: var(--bg-void); color: var(--text-primary); font-size: var(--fs-xs); }
.ghost-btn { white-space: nowrap; text-decoration: none; display: inline-flex; align-items: center; background: none; border: 1px solid var(--border-default); border-radius: var(--radius-sm); padding: 8px 14px; font-size: var(--fs-sm); color: var(--text-secondary); cursor: pointer; }

.stats-row { display: flex; gap: var(--sp-md); margin-bottom: var(--sp-lg); }
.stat { display: flex; flex-direction: column; background: var(--bg-elevated); border: 1px solid var(--border-muted); border-radius: var(--radius-md); padding: var(--sp-sm) var(--sp-lg); min-width: 80px; }
.stat-num { font-size: var(--fs-md); font-weight: 700; }
.stat-label { font-size: var(--fs-xs); color: var(--text-muted); }

.trial-row { display: flex; align-items: center; gap: var(--sp-sm); flex-wrap: wrap; label { font-size: var(--fs-sm); color: var(--text-secondary); } }
.ctrl { padding: 8px 10px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); background: var(--bg-void); color: var(--text-primary); font-size: var(--fs-sm); }
.ctrl.small { width: 90px; }
.unit { font-size: var(--fs-sm); color: var(--text-muted); }

.action-row { display: flex; align-items: center; gap: var(--sp-md); margin-top: var(--sp-md); }
.primary-btn { background: var(--accent-ember); color: #fff; border: none; border-radius: var(--radius-md); padding: 10px 22px; font-size: var(--fs-base); font-weight: 600; cursor: pointer; }
.danger-btn { background: transparent; color: var(--accent-cinnabar); border: 1px solid var(--accent-cinnabar); border-radius: var(--radius-md); padding: 9px 18px; font-size: var(--fs-sm); cursor: pointer; }
.text-link { font-size: var(--fs-sm); color: var(--accent-ember); text-decoration: none; }

.status-dot { font-size: var(--fs-xs); padding: 2px 10px; border-radius: 999px; background: var(--border-muted); color: var(--text-muted); }
.status-dot.active { background: rgba(5,150,105,.12); color: var(--accent-jade); }
.status-dot.disabled { background: rgba(220,38,38,.1); color: var(--accent-cinnabar); }
</style>
