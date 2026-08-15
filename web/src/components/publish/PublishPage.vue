<template>
  <div class="publish-page page-container">
    <header class="page-header">
      <h1 class="page-title">成书发布</h1>
      <span class="page-subtitle">质量门禁 · 平台规范导出 · 发布记录</span>
    </header>

    <div class="page-content">
      <!-- Step 1: preflight -->
      <section class="card">
        <h3 class="section-label">第一步 · 发布前检查</h3>
        <div class="row">
          <button class="btn-primary" :disabled="preflightLoading" @click="doPreflight">
            {{ preflightLoading ? '检查中…' : '运行质量门禁' }}
          </button>
          <span v-if="gate" class="gate-badge" :class="gate.ok ? 'gate-ok' : 'gate-fail'">
            {{ gate.ok ? '通过 — 可导出' : '未通过 — 请先修复' }}
          </span>
        </div>

        <div v-if="gate" class="gate-result">
          <div class="stats-grid">
            <div class="stat">
              <span class="stat-num">{{ gate.stats.chapters }}</span>
              <span class="stat-label">章节</span>
            </div>
            <div class="stat">
              <span class="stat-num">{{ formatNum(gate.stats.total_words) }}</span>
              <span class="stat-label">总字数</span>
            </div>
            <div class="stat">
              <span class="stat-num">{{ gate.stats.volume_count }}</span>
              <span class="stat-label">分卷</span>
            </div>
            <div class="stat">
              <span class="stat-num">{{ gate.stats.avg_chapter_words }}</span>
              <span class="stat-label">平均章字数</span>
            </div>
          </div>

          <div v-if="gate.errors.length" class="msg-list msg-error">
            <p v-for="(e, i) in gate.errors" :key="i">{{ e }}</p>
          </div>
          <div v-if="gate.warnings.length" class="msg-list msg-warn">
            <p v-for="(w, i) in gate.warnings" :key="i">{{ w }}</p>
          </div>
          <div v-if="gate.sensitive_hits.length" class="msg-list msg-warn">
            <p>
              敏感词命中：
              <span v-for="(h, i) in gate.sensitive_hits.slice(0, 8)" :key="i" class="hit">
                「{{ h.word }}」第{{ h.chapter_index + 1 }}章×{{ h.count }}
              </span>
            </p>
          </div>
        </div>
      </section>

      <!-- Step 2: export -->
      <section class="card">
        <h3 class="section-label">第二步 · 选择平台导出</h3>
        <div v-if="platforms.length === 0" class="hint">加载平台列表…</div>
        <div v-else class="platform-grid">
          <label
            v-for="p in platforms"
            :key="p.platform"
            class="platform-card"
            :class="{ 'is-selected': platform === p.platform }"
          >
            <input type="radio" :value="p.platform" v-model="platform" />
            <div>
              <b>{{ p.display_name }}</b>
              <span class="platform-spec">
                {{ p.formats.toUpperCase() }} · {{ p.encoding }}
                <template v-if="p.chapter_max_words"> · 建议单章≤{{ p.chapter_max_words }}字</template>
                <template v-if="p.supports_volumes"> · 支持分卷</template>
              </span>
              <span class="platform-notes">{{ p.notes }}</span>
            </div>
          </label>
        </div>

        <div class="row">
          <button
            class="btn-primary"
            :disabled="exporting || !platform"
            @click="doExport"
          >
            {{ exporting ? '导出打包中…' : '一键导出下载' }}
          </button>
          <span class="hint">
            导出包含正文、简介、封面占位图与发布说明，前往平台作家后台手动上传
          </span>
        </div>
        <div v-if="exportError" class="msg-list msg-error"><p>{{ exportError }}</p></div>
      </section>

      <!-- Step 3: records -->
      <section class="card">
        <h3 class="section-label">发布记录</h3>
        <div v-if="records.length === 0" class="hint">暂无发布记录</div>
        <table v-else class="records-table">
          <thead>
            <tr>
              <th>时间</th><th>平台</th><th>状态</th><th>章节/字数</th><th>平台侧</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td class="cell-time">{{ formatTime(r.created_at) }}</td>
              <td>{{ platformName(r.platform) }}</td>
              <td>
                <span class="stage-badge" :class="`stage-${r.stage}`">{{ stageLabel(r.stage) }}</span>
              </td>
              <td class="cell-meta">
                {{ (r.export_meta as any)?.chapters ?? '—' }}章 /
                {{ formatNum((r.export_meta as any)?.words ?? 0) }}字
              </td>
              <td>
                <a v-if="r.target_url" :href="r.target_url" target="_blank" class="link">
                  {{ r.target_book_id || '链接' }}
                </a>
                <span v-else class="hint">未回填</span>
              </td>
              <td>
                <button
                  v-if="r.stage !== 'published'"
                  class="btn-sm"
                  @click="openBackfill(r)"
                >
                  回填链接
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <!-- Backfill dialog -->
    <div v-if="backfillOpen" class="modal-scrim" @click.self="backfillOpen = false">
      <div class="modal-card">
        <h3>回填发布结果</h3>
        <p class="hint">在平台作家后台完成上传与审核后，把书籍链接 / ID 填回来。</p>
        <label class="field-label">平台侧书籍链接</label>
        <input v-model="backfillForm.target_url" class="field-input" placeholder="https://…" />
        <label class="field-label">平台侧书籍 ID（可选）</label>
        <input v-model="backfillForm.target_book_id" class="field-input" />
        <div class="modal-actions">
          <button class="btn-ghost" @click="backfillOpen = false">取消</button>
          <button class="btn-primary" @click="doBackfill">保存并标记已发布</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  getPlatforms,
  runPreflight,
  exportNovel,
  getPublicationRecords,
  backfillRecord,
  type PlatformProfile,
  type PreflightResult,
  type PublicationRecord,
} from '@/api/publish'

const route = useRoute()
const novelId = String(route.params.novelId || '')

const platforms = ref<PlatformProfile[]>([])
const platform = ref('fanqie')
const gate = ref<PreflightResult | null>(null)
const preflightLoading = ref(false)
const exporting = ref(false)
const exportError = ref('')
const records = ref<PublicationRecord[]>([])

const backfillOpen = ref(false)
const backfillTarget = ref<PublicationRecord | null>(null)
const backfillForm = reactive({ target_url: '', target_book_id: '' })

function formatNum(n: number) {
  if (!n) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(n)
}

function formatTime(ts: string) {
  return (ts || '').replace('T', ' ').slice(0, 16)
}

function platformName(p: string) {
  return platforms.value.find((x) => x.platform === p)?.display_name || p
}

function stageLabel(stage: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    exporting: '导出中',
    exported: '已导出',
    publishing: '发布中',
    published: '已发布',
    failed: '失败',
  }
  return map[stage] || stage
}

async function doPreflight() {
  preflightLoading.value = true
  exportError.value = ''
  try {
    const { data } = await runPreflight(novelId, platform.value)
    gate.value = data
  } catch (e: any) {
    exportError.value = e.response?.data?.detail?.message || '检查失败'
  } finally {
    preflightLoading.value = false
  }
}

async function doExport() {
  exporting.value = true
  exportError.value = ''
  try {
    const resp = await exportNovel(novelId, platform.value)
    // Download blob
    const disposition: string = resp.headers['content-disposition'] || ''
    let filename = `${novelId}-${platform.value}-export.zip`
    const m = disposition.match(/filename\*=UTF-8''([^;]+)/)
    if (m) filename = decodeURIComponent(m[1])
    const url = URL.createObjectURL(new Blob([resp.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    await loadRecords()
  } catch (e: any) {
    // blob responses carry JSON error bodies — decode them
    try {
      const text = await e.response?.data?.text?.()
      const parsed = text ? JSON.parse(text) : null
      const detail = parsed?.detail
      exportError.value =
        typeof detail === 'object'
          ? `${detail.message}：${(detail.errors || []).join('；')}`
          : detail || '导出失败'
    } catch {
      exportError.value = '导出失败'
    }
  } finally {
    exporting.value = false
  }
}

async function loadRecords() {
  const { data } = await getPublicationRecords(novelId)
  records.value = data.records || []
}

function openBackfill(r: PublicationRecord) {
  backfillTarget.value = r
  backfillForm.target_url = r.target_url
  backfillForm.target_book_id = r.target_book_id
  backfillOpen.value = true
}

async function doBackfill() {
  if (!backfillTarget.value) return
  await backfillRecord(backfillTarget.value.id, {
    target_url: backfillForm.target_url,
    target_book_id: backfillForm.target_book_id,
  })
  backfillOpen.value = false
  await loadRecords()
}

onMounted(async () => {
  const { data } = await getPlatforms()
  platforms.value = data.platforms || []
  await loadRecords()
})
</script>

<style scoped lang="scss">
.publish-page {
  max-width: 900px;
}

.card {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  padding: var(--sp-md);
  margin-bottom: var(--sp-md);
  box-shadow: var(--shadow-sm);
}

.section-label {
  margin: 0 0 var(--sp-md);
  font-size: var(--fs-base);
}

.row {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  flex-wrap: wrap;
  margin-bottom: var(--sp-sm);
}

.btn-primary {
  background: var(--accent-ember);
  border: none;
  color: #fff;
  padding: 9px 18px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--fs-sm);

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.hint {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.gate-badge {
  font-size: var(--fs-sm);
  padding: 4px 10px;
  border-radius: var(--radius-badge);
}

.gate-ok {
  color: var(--accent-jade);
  background: rgba(5, 150, 105, 0.1);
}

.gate-fail {
  color: var(--accent-cinnabar);
  background: rgba(220, 38, 38, 0.08);
}

.stats-grid {
  display: flex;
  gap: var(--sp-sm);
  flex-wrap: wrap;
  margin: var(--sp-md) 0;
}

.stat {
  flex: 1;
  min-width: 100px;
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

.msg-list {
  border-radius: var(--radius-sm);
  padding: var(--sp-sm) var(--sp-md);
  font-size: var(--fs-sm);
  margin-bottom: var(--sp-sm);

  p {
    margin: var(--sp-xs) 0;
  }
}

.msg-error {
  background: rgba(220, 38, 38, 0.06);
  color: var(--accent-cinnabar);
}

.msg-warn {
  background: rgba(202, 138, 4, 0.08);
  color: #a16207;

  .hit {
    margin-right: var(--sp-sm);
  }
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--sp-sm);
  margin-bottom: var(--sp-md);
}

.platform-card {
  display: flex;
  gap: var(--sp-sm);
  align-items: flex-start;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: var(--sp-md);
  cursor: pointer;
  font-size: var(--fs-sm);

  input {
    margin-top: 3px;
    accent-color: var(--accent-ember);
  }

  div {
    display: flex;
    flex-direction: column;
    gap: var(--sp-xs);
  }

  &.is-selected {
    border-color: var(--border-active);
    background: var(--accent-ember-dim);
  }

  .platform-spec {
    color: var(--text-secondary);
    font-size: var(--fs-xs);
  }

  .platform-notes {
    color: var(--text-muted);
    font-size: var(--fs-xs);
    line-height: 1.5;
  }
}

.records-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-sm);

  th, td {
    text-align: left;
    padding: 8px;
    border-bottom: 1px solid var(--border-muted);
  }

  th {
    color: var(--text-muted);
    font-weight: 500;
  }

  .cell-time, .cell-meta {
    font-family: var(--font-data);
    font-size: var(--fs-xs);
  }

  .link {
    color: var(--accent-blue);
  }
}

.stage-badge {
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: var(--radius-badge);
  background: var(--bg-elevated);
  color: var(--text-secondary);
}

.stage-exported {
  color: var(--accent-blue);
  background: rgba(37, 99, 235, 0.08);
}

.stage-published {
  color: var(--accent-jade);
  background: rgba(5, 150, 105, 0.1);
}

.stage-failed {
  color: var(--accent-cinnabar);
  background: rgba(220, 38, 38, 0.08);
}

.btn-sm {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--fs-xs);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

// modal
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

  h3 {
    margin: 0 0 var(--sp-sm);
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
  box-sizing: border-box;
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
</style>
