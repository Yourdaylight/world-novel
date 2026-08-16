<template>
  <div class="publish-page">
    <header class="page-head">
      <h1 class="page-title">成书发布</h1>
      <p class="page-sub">
        番茄 / 七猫等平台暂无开放作者 API，系统按平台规范一键导出成稿，你在平台作家后台上传即可。
      </p>
    </header>

    <div v-if="loading" class="muted">正在检查成书质量…</div>

    <template v-else>
      <!-- Quality gate -->
      <section class="card">
        <div class="card-head">
          <h2>发布前质量门禁</h2>
          <button class="ghost-btn" @click="runGate">重新检查</button>
        </div>

        <div class="stat-row">
          <div class="stat"><span class="stat-num font-data">{{ verdict?.stats.chapters ?? 0 }}</span><span class="stat-label">章节</span></div>
          <div class="stat"><span class="stat-num font-data">{{ (verdict?.stats.total_words ?? 0).toLocaleString() }}</span><span class="stat-label">总字数</span></div>
          <div class="stat"><span class="stat-num font-data">{{ verdict?.stats.volumes ?? 0 }}</span><span class="stat-label">卷</span></div>
          <div class="stat" :class="verdict?.ok ? 'ok' : 'bad'">
            <span class="stat-num">{{ verdict?.ok ? '通过' : '未过' }}</span><span class="stat-label">门禁</span>
          </div>
        </div>

        <div v-for="e in verdict?.errors" :key="e.code" class="issue error">
          <span class="issue-tag">阻断</span>{{ e.message }}
        </div>
        <div v-for="w in verdict?.warnings" :key="w.code" class="issue warn">
          <span class="issue-tag">提醒</span>{{ w.message }}
        </div>
        <div v-if="verdict && !verdict.errors.length && !verdict.warnings.length" class="issue ok-text">
          未发现问题，可以发布。
        </div>
      </section>

      <!-- Platform + export -->
      <section class="card">
        <div class="card-head"><h2>选择导出平台</h2></div>
        <div class="platform-grid">
          <button
            v-for="p in PLATFORM_OPTIONS"
            :key="p.key"
            class="platform-card"
            :class="{ selected: platform === p.key }"
            @click="selectPlatform(p.key)"
          >
            <span class="platform-label">{{ p.label }}</span>
            <span class="platform-desc">{{ p.description }}</span>
          </button>
        </div>

        <div class="action-row">
          <button
            class="primary-btn"
            :disabled="!verdict?.ok || exporting"
            @click="doExport"
          >
            {{ exporting ? '正在打包…' : `一键导出${platformLabel}` }}
          </button>
          <router-link class="text-link" :to="{ name: 'share', params: { novelId } }">
            或生成公开分享链接 →
          </router-link>
        </div>
        <p v-if="message" class="action-msg" :class="messageKind">{{ message }}</p>
      </section>

      <!-- Records -->
      <section class="card">
        <div class="card-head"><h2>发布记录</h2></div>
        <div v-if="!records.length" class="muted">还没有导出记录。</div>
        <table v-else class="record-table">
          <thead><tr><th>时间</th><th>平台</th><th>状态</th><th>规格</th></tr></thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td class="font-data">{{ fmtTime(r.created_at) }}</td>
              <td>{{ platformName(r.platform) }}</td>
              <td><span class="stage" :class="r.stage">{{ stageLabel(r.stage) }}</span></td>
              <td class="font-data muted">
                {{ (r.export_meta as any)?.chapters ?? '-' }}章 ·
                {{ Number((r.export_meta as any)?.bytes ?? 0) }}B
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  PLATFORM_OPTIONS,
  runPreflight,
  exportNovel,
  listRecords,
  type PreflightVerdict,
  type PublicationRecord,
} from '@/api/publish'
import axios from 'axios'

const route = useRoute()
const novelId = String(route.params.novelId || '')

const loading = ref(true)
const exporting = ref(false)
const platform = ref('bundle')
const verdict = ref<PreflightVerdict | null>(null)
const records = ref<PublicationRecord[]>([])
const message = ref('')
const messageKind = ref<'ok' | 'err'>('ok')

const platformLabel = computed(
  () => PLATFORM_OPTIONS.find(p => p.key === platform.value)?.label || '',
)

async function runGate() {
  loading.value = true
  try {
    verdict.value = await runPreflight(novelId, platform.value === 'bundle' ? 'fanqie' : platform.value)
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) {
      verdict.value = null
      message.value = '该小说尚无成文章节，请先生成。'
      messageKind.value = 'err'
    }
  } finally {
    loading.value = false
  }
}

function selectPlatform(key: string) {
  platform.value = key
  runGate()
}

async function doExport() {
  exporting.value = true
  message.value = ''
  try {
    await exportNovel(novelId, platform.value)
    message.value = '导出成功，文件已开始下载。请到对应平台作家后台上传。'
    messageKind.value = 'ok'
    records.value = await listRecords(novelId)
  } catch (e: any) {
    if (axios.isAxiosError(e) && e.response?.status === 422) {
      message.value = '质量门禁未通过，请先修复空章/断章后再导出。'
    } else {
      message.value = e?.message || '导出失败'
    }
    messageKind.value = 'err'
  } finally {
    exporting.value = false
  }
}

function platformName(key: string) {
  return PLATFORM_OPTIONS.find(p => p.key === key)?.label || key
}
function stageLabel(stage: string) {
  return { exported: '已导出', published: '已发布', failed: '失败' }[stage] || stage
}
function fmtTime(iso: string) {
  return iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'
}

onMounted(async () => {
  await Promise.all([runGate(), listRecords(novelId).then(r => (records.value = r)).catch(() => undefined)])
})
</script>

<style scoped lang="scss">
.publish-page { max-width: 900px; display: flex; flex-direction: column; gap: var(--sp-lg); }
.page-head .page-title { font-family: var(--font-display); font-size: var(--fs-xl); font-weight: 400; margin: 0 0 var(--sp-xs); }
.page-sub { color: var(--text-secondary); font-size: var(--fs-sm); margin: 0; line-height: 1.7; }
.card { background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); padding: var(--sp-lg); box-shadow: var(--shadow-sm); }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--sp-md); h2 { font-size: var(--fs-md); margin: 0; } }
.muted { color: var(--text-muted); font-size: var(--fs-sm); }

.stat-row { display: flex; gap: var(--sp-md); margin-bottom: var(--sp-md); }
.stat { display: flex; flex-direction: column; gap: 2px; background: var(--bg-elevated); border: 1px solid var(--border-muted); border-radius: var(--radius-md); padding: var(--sp-sm) var(--sp-lg); min-width: 84px; }
.stat-num { font-size: var(--fs-md); font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: var(--fs-xs); color: var(--text-muted); }
.stat.ok .stat-num { color: var(--accent-jade); }
.stat.bad .stat-num { color: var(--accent-cinnabar); }

.issue { font-size: var(--fs-sm); padding: var(--sp-sm) var(--sp-md); border-radius: var(--radius-sm); margin-bottom: 6px; line-height: 1.6; }
.issue.error { background: rgba(220,38,38,0.07); color: var(--accent-cinnabar); }
.issue.warn { background: rgba(217,119,6,0.07); color: #b45309; }
.issue.ok-text { color: var(--accent-jade); font-size: var(--fs-sm); }
.issue-tag { display: inline-block; font-size: var(--fs-xs); padding: 1px 6px; border-radius: 4px; background: currentColor; color: #fff; margin-right: 8px; opacity: 0.85; }

.platform-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--sp-sm); }
.platform-card { display: flex; flex-direction: column; gap: 4px; text-align: left; padding: var(--sp-md); border-radius: var(--radius-md); border: 1px solid var(--border-default); background: var(--bg-elevated); cursor: pointer; transition: border-color .15s; }
.platform-card.selected { border-color: var(--accent-ember); box-shadow: 0 0 0 1px var(--accent-ember) inset; }
.platform-label { font-size: var(--fs-base); font-weight: 600; color: var(--text-primary); }
.platform-desc { font-size: var(--fs-xs); color: var(--text-secondary); line-height: 1.5; }

.action-row { display: flex; align-items: center; gap: var(--sp-md); margin-top: var(--sp-lg); }
.primary-btn { background: var(--accent-ember); color: #fff; border: none; border-radius: var(--radius-md); padding: 10px 22px; font-size: var(--fs-base); font-weight: 600; cursor: pointer; &:disabled { opacity: .5; cursor: not-allowed; } }
.ghost-btn { background: none; border: 1px solid var(--border-default); border-radius: var(--radius-sm); padding: 5px 12px; font-size: var(--fs-xs); color: var(--text-secondary); cursor: pointer; }
.text-link { font-size: var(--fs-sm); color: var(--accent-ember); text-decoration: none; }
.action-msg { font-size: var(--fs-sm); margin-top: var(--sp-sm); &.ok { color: var(--accent-jade); } &.err { color: var(--accent-cinnabar); } }

.record-table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
.record-table th { text-align: left; color: var(--text-muted); font-weight: 500; font-size: var(--fs-xs); padding: 6px 8px; border-bottom: 1px solid var(--border-default); }
.record-table td { padding: 8px; border-bottom: 1px solid var(--border-muted); }
.stage { font-size: var(--fs-xs); padding: 2px 8px; border-radius: 4px; background: var(--accent-ember-dim); color: var(--accent-ember); }
.stage.published { background: rgba(5,150,105,.1); color: var(--accent-jade); }
</style>
