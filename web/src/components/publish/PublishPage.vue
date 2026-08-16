<template>
  <div class="publish-page page-container">
    <header class="page-header">
      <h1 class="page-title">成书发布</h1>
      <span class="page-subtitle">质量门禁 · 平台导出 · 发布记录</span>
    </header>

    <div class="page-content publish-grid">
      <!-- Left: export wizard -->
      <div class="publish-main">
        <section class="card">
          <h3 class="section-label">选择发布平台</h3>
          <p class="hint-text">
            番茄、七猫等平台均未开放写作 API，本期提供 L0 一键导出：按平台规范生成文件包，
            请在对应作家后台手动上传。L1 半自动发布为远期能力（独立浏览器容器）。
          </p>
          <div class="platform-list">
            <label
              v-for="p in platforms"
              :key="p.key"
              class="platform-item"
              :class="{ active: platform === p.key }"
            >
              <input v-model="platform" type="radio" name="platform" :value="p.key" />
              <span class="platform-label">{{ p.label }}</span>
              <span class="platform-meta font-data">
                {{ p.format.toUpperCase() }} · {{ p.encoding.toUpperCase() }}
                <template v-if="p.chapter_word_hint"> · 单章建议≤{{ p.chapter_word_hint }}字</template>
              </span>
            </label>
          </div>
        </section>

        <section class="card">
          <h3 class="section-label">发布前质量门禁</h3>
          <div class="action-row">
            <button class="btn-primary" :disabled="checking" @click="doPreflight">
              {{ checking ? '检查中…' : '运行预检' }}
            </button>
            <button
              class="btn-export"
              :disabled="!preflight?.ok || exporting"
              @click="doExport"
            >
              {{ exporting ? '导出中…' : '一键导出并下载' }}
            </button>
          </div>

          <div v-if="preflight" class="preflight-result">
            <div v-if="!preflight.ok" class="result-block result-error">
              <strong>无法导出，请先修复：</strong>
              <ul><li v-for="(e, i) in preflight.errors" :key="i">{{ e }}</li></ul>
            </div>
            <template v-else>
              <div class="stat-grid">
                <div class="stat-cell"><span class="stat-num font-data">{{ preflight.stats.chapters }}</span><span class="stat-label">章节</span></div>
                <div class="stat-cell"><span class="stat-num font-data">{{ preflight.stats.total_words.toLocaleString() }}</span><span class="stat-label">字数</span></div>
                <div class="stat-cell"><span class="stat-num font-data">{{ preflight.stats.volumes }}</span><span class="stat-label">分卷</span></div>
                <div class="stat-cell"><span class="stat-num font-data">{{ preflight.stats.encoding }}</span><span class="stat-label">编码</span></div>
              </div>
              <div v-if="preflight.warnings.length" class="result-block result-warn">
                <strong>警告（不阻止导出）：</strong>
                <ul><li v-for="(w, i) in preflight.warnings" :key="i">{{ w }}</li></ul>
              </div>
              <div v-else class="result-ok">质量门禁通过，可以导出</div>
            </template>
          </div>
        </section>
      </div>

      <!-- Right: history -->
      <div class="publish-side">
        <section class="card">
          <h3 class="section-label">发布记录</h3>
          <div v-if="records.length === 0" class="empty-hint">暂无导出记录</div>
          <ul class="record-list">
            <li v-for="r in records" :key="r.id" class="record-item">
              <div class="record-head">
                <span class="record-platform">{{ platformLabel(r.platform) }}</span>
                <span class="record-stage" :class="'stage-' + r.stage">{{ stageLabel(r.stage) }}</span>
              </div>
              <div class="record-meta font-data">
                {{ r.created_at }} · {{ formatMeta(r.export_meta) }}
              </div>
              <div v-if="safeUrl(r.target_url)" class="record-link">
                <a :href="r.target_url" target="_blank" rel="noopener noreferrer">{{ r.target_url }}</a>
              </div>
              <div v-else-if="r.target_url" class="record-link record-link--text">{{ r.target_url }}</div>
              <div class="record-actions">
                <button
                  v-if="r.stage === 'exported'"
                  class="btn-link"
                  @click="openBackfill(r)"
                >回填平台链接</button>
              </div>
            </li>
          </ul>
        </section>
      </div>
    </div>

    <!-- Backfill dialog -->
    <el-dialog v-model="backfillVisible" title="回填平台发布信息" width="420px">
      <div class="backfill-form">
        <label>平台书 ID（可选）</label>
        <input v-model="backfillForm.target_book_id" class="text-input" placeholder="如番茄作品 ID" />
        <label>作品链接（可选）</label>
        <input v-model="backfillForm.target_url" class="text-input" placeholder="https://…" />
      </div>
      <template #footer>
        <button class="btn-secondary" @click="backfillVisible = false">取消</button>
        <button class="btn-primary" @click="submitBackfill">保存</button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  listPlatforms, runPreflight, exportNovel, listRecords, backfillRecord,
  type PlatformProfile, type PreflightResult, type PublishRecord,
} from '@/api/publish'

const route = useRoute()
const novelId = () => (route.params.novelId as string)

const platforms = ref<PlatformProfile[]>([])
const platform = ref('fanqie')
const checking = ref(false)
const exporting = ref(false)
const preflight = ref<PreflightResult | null>(null)
const records = ref<PublishRecord[]>([])

const backfillVisible = ref(false)
const backfillForm = ref({ id: '', target_book_id: '', target_url: '' })

// Blob requests deliver even error bodies as Blob — parse them back to JSON
async function parseErrorBlob(error: any): Promise<any> {
  const data = error.response?.data
  if (data instanceof Blob) {
    try { return JSON.parse(await data.text()) } catch { return null }
  }
  return data || null
}

// Render guard: only ever treat http(s) values as clickable links
function safeUrl(url: string): boolean {
  return /^https?:\/\//i.test(url || '')
}

function platformLabel(key: string) {
  return platforms.value.find((p) => p.key === key)?.label || key
}

function stageLabel(stage: string) {
  return { exported: '已导出', published: '已发布', failed: '失败', exporting: '导出中' }[stage] || stage
}

function formatMeta(meta: Record<string, unknown>): string {
  const parts: string[] = []
  if (meta.chapters != null) parts.push(`${meta.chapters}章`)
  if (meta.words != null) parts.push(`约${Number(meta.words).toLocaleString()}字`)
  if (meta.encoding) parts.push(String(meta.encoding).toUpperCase())
  return parts.join(' · ')
}

async function doPreflight() {
  checking.value = true
  preflight.value = null
  try {
    preflight.value = await runPreflight(novelId(), platform.value)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '预检失败')
  } finally {
    checking.value = false
  }
}

async function doExport() {
  exporting.value = true
  try {
    const { blob, filename } = await exportNovel(novelId(), platform.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)  // Firefox requires the anchor be in the DOM
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功，已开始下载')
    await loadRecords()
  } catch (e: any) {
    const data = await parseErrorBlob(e)
    if (e.response?.status === 409 && data?.preflight) {
      preflight.value = data.preflight
      ElMessage.error('质量门禁未通过，请查看预检详情')
    } else {
      ElMessage.error(data?.error || '导出失败')
    }
  } finally {
    exporting.value = false
  }
}

// Switching platform invalidates the previous platform's preflight result
watch(platform, () => { preflight.value = null })

function openBackfill(r: PublishRecord) {
  backfillForm.value = { id: r.id, target_book_id: r.target_book_id || '', target_url: r.target_url || '' }
  backfillVisible.value = true
}

async function submitBackfill() {
  try {
    await backfillRecord(backfillForm.value.id, {
      target_book_id: backfillForm.value.target_book_id,
      target_url: backfillForm.value.target_url,
    })
    ElMessage.success('已标记为已发布')
    backfillVisible.value = false
    await loadRecords()
  } catch {
    ElMessage.error('保存失败')
  }
}

async function loadRecords() {
  try {
    records.value = await listRecords(novelId())
  } catch { /* ignore */ }
}

onMounted(async () => {
  try {
    platforms.value = await listPlatforms()
  } catch { /* ignore */ }
  await loadRecords()
})
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

.publish-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: var(--sp-md);
  align-items: start;
}

.hint-text {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0 0 var(--sp-md);
}

.platform-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
}

.platform-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: 10px 12px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--duration-fast) ease;

  &.active {
    border-color: var(--accent-ember);
    background: var(--accent-ember-dim);
  }

  input { accent-color: var(--accent-ember); }
}

.platform-label {
  font-size: var(--fs-base);
  font-weight: 550;
  color: var(--text-primary);
}

.platform-meta {
  margin-left: auto;
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.action-row {
  display: flex;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-md);
}

.btn-primary,
.btn-export,
.btn-secondary {
  height: 34px;
  padding: 0 16px;
  border-radius: var(--radius-md);
  font-size: var(--fs-sm);
  font-weight: 550;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--duration-fast) ease;
}

.btn-primary {
  background: var(--accent-ember);
  color: var(--text-inverse);

  &:hover { background: #b45309; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.btn-export {
  background: transparent;
  border-color: var(--accent-ember);
  color: var(--accent-ember);

  &:hover:not(:disabled) { background: var(--accent-ember-dim); }
  &:disabled { opacity: 0.4; cursor: not-allowed; }
}

.btn-secondary {
  background: var(--bg-elevated);
  border-color: var(--border-default);
  color: var(--text-secondary);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-sm);
  margin-bottom: var(--sp-md);
}

.stat-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--sp-sm);
  border: 1px solid var(--border-muted);
  border-radius: var(--radius-md);
}

.stat-num { font-size: var(--fs-md); font-weight: 650; color: var(--text-primary); }
.stat-label { font-size: var(--fs-xs); color: var(--text-muted); }

.result-block {
  border-radius: var(--radius-md);
  padding: var(--sp-sm) var(--sp-md);
  font-size: var(--fs-sm);
  line-height: 1.7;

  ul { margin: var(--sp-xs) 0 0; padding-left: var(--sp-lg); }
}

.result-error {
  background: rgba(220, 38, 38, 0.06);
  border: 1px solid rgba(220, 38, 38, 0.3);
  color: var(--text-primary);
}

.result-warn {
  background: rgba(202, 138, 4, 0.06);
  border: 1px solid rgba(202, 138, 4, 0.3);
}

.result-ok {
  font-size: var(--fs-sm);
  color: var(--accent-jade);
}

.empty-hint {
  font-size: var(--fs-sm);
  color: var(--text-muted);
  padding: var(--sp-md) 0;
}

.record-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}

.record-item {
  border: 1px solid var(--border-muted);
  border-radius: var(--radius-md);
  padding: var(--sp-sm) var(--sp-md);
}

.record-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
}

.record-platform { font-size: var(--fs-sm); font-weight: 550; color: var(--text-primary); }

.record-stage {
  font-size: var(--fs-xs);
  padding: 1px 8px;
  border-radius: 6px;

  &.stage-exporting,
  &.stage-exported { background: rgba(37, 99, 235, 0.1); color: var(--accent-blue); }
  &.stage-published { background: rgba(5, 150, 105, 0.1); color: var(--accent-jade); }
  &.stage-failed { background: rgba(220, 38, 38, 0.1); color: var(--accent-cinnabar); }
}

.record-meta { font-size: var(--fs-xs); color: var(--text-muted); }

.record-link {
  margin-top: 4px;
  font-size: var(--fs-xs);
  a { color: var(--accent-blue); word-break: break-all; }

  &--text { color: var(--text-muted); word-break: break-all; }
}

.record-actions { margin-top: 4px; }

.btn-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--accent-ember);
  font-size: var(--fs-xs);
  cursor: pointer;

  &:hover { text-decoration: underline; }
}

.backfill-form {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label { font-size: var(--fs-sm); color: var(--text-secondary); }
}

.text-input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-void);
  color: var(--text-primary);
  font-size: var(--fs-sm);
  margin-bottom: var(--sp-sm);

  &:focus { outline: none; border-color: var(--accent-ember); }
}

@media (max-width: 900px) {
  .publish-grid { grid-template-columns: 1fr; }
}
</style>
