<template>
  <div class="publish-page page-container">
    <header class="page-header">
      <div class="header-title">
        <h1 class="page-title">成书发布</h1>
        <p class="page-subtitle">
          质量门禁 → 按平台规范导出（L0）→ 到作家后台手动上传。番茄/七猫暂无开放 API，全自动直发为远期能力。
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="loadRecords" :loading="recordsLoading">刷新记录</el-button>
      </div>
    </header>

    <!-- 平台选择 -->
    <section class="card">
      <h2 class="section-title">① 选择发布平台</h2>
      <div class="platform-grid">
        <div
          v-for="p in platforms"
          :key="p.key"
          class="platform-card"
          :class="{ active: selectedPlatform === p.key }"
          @click="selectedPlatform = p.key"
        >
          <div class="platform-name">{{ p.name }}</div>
          <div class="platform-format">{{ p.output_format.toUpperCase() }} · {{ p.encoding }}</div>
          <p class="platform-desc">{{ p.description }}</p>
          <a
            v-if="p.writer_url"
            :href="p.writer_url"
            target="_blank"
            rel="noopener"
            class="platform-link"
            @click.stop
          >
            作家后台 ↗
          </a>
        </div>
      </div>
    </section>

    <!-- 质量门禁 -->
    <section class="card">
      <div class="section-head">
        <h2 class="section-title">② 发布前质量门禁</h2>
        <el-button type="primary" plain @click="runCheck" :loading="checking">
          运行检查
        </el-button>
      </div>

      <div v-if="report" class="report">
        <div class="report-stats">
          <div class="stat"><span class="stat-num">{{ report.stats.chapter_count }}</span><span class="stat-label">已渲染章节</span></div>
          <div class="stat"><span class="stat-num">{{ report.stats.planned_count }}</span><span class="stat-label">计划章节</span></div>
          <div class="stat"><span class="stat-num">{{ report.stats.total_words.toLocaleString() }}</span><span class="stat-label">总字数</span></div>
          <div class="stat"><span class="stat-num">{{ report.stats.empty_chapters }}</span><span class="stat-label">空章节</span></div>
        </div>

        <el-alert
          v-if="report.errors.length"
          type="error"
          :closable="false"
          show-icon
          title="必须修复后才能导出"
        >
          <ul class="issue-list">
            <li v-for="(e, i) in report.errors" :key="i">{{ e }}</li>
          </ul>
        </el-alert>

        <el-alert
          v-if="report.warnings.length"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 10px"
          title="警告（不阻断导出，请人工复核）"
        >
          <ul class="issue-list">
            <li v-for="(w, i) in report.warnings" :key="i">{{ w }}</li>
          </ul>
        </el-alert>

        <el-alert
          v-if="report.ok && !report.warnings.length"
          type="success"
          :closable="false"
          show-icon
          title="检查通过，可以导出"
          style="margin-top: 10px"
        />
      </div>
    </section>

    <!-- 导出 -->
    <section class="card">
      <h2 class="section-title">③ 一键导出</h2>
      <p class="section-hint">
        导出物按所选平台规范生成（分卷 / 编码 / 简介 / 封面占位），下载后到对应作家后台上传。
      </p>
      <el-button
        class="btn-gradient"
        :disabled="!selectedPlatform"
        :loading="exporting"
        @click="onExport"
      >
        导出 {{ currentPlatform?.name || '' }}
      </el-button>
      <span v-if="lastRecordId" class="last-record">已生成发布记录 {{ lastRecordId }}</span>
    </section>

    <!-- 发布记录 -->
    <section class="card">
      <h2 class="section-title">发布记录</h2>
      <el-table :data="records" v-loading="recordsLoading" style="width: 100%">
        <el-table-column label="时间" prop="created_at" width="170" />
        <el-table-column label="平台" prop="platform" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.stage === 'published' ? 'success' : row.stage === 'failed' ? 'danger' : 'info'">
              {{ stageLabel(row.stage) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="规格">
          <template #default="{ row }">
            {{ row.export_meta?.chapters }} 章 · {{ row.export_meta?.words?.toLocaleString() }} 字 · {{ row.export_meta?.format }}
          </template>
        </el-table-column>
        <el-table-column label="平台链接" width="220">
          <template #default="{ row }">
            <a v-if="row.target_url" :href="row.target_url" target="_blank" rel="noopener">{{ row.target_url }}</a>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-button size="small" text @click="openBackfill(row)">回填链接</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 回填对话框 -->
    <el-dialog v-model="backfillOpen" title="回填平台发布信息" width="460px">
      <el-form label-position="top">
        <el-form-item label="平台书 ID（可选）">
          <el-input v-model="backfillForm.target_book_id" placeholder="番茄/七猫后台的作品 ID" />
        </el-form-item>
        <el-form-item label="作品链接（可选）">
          <el-input v-model="backfillForm.target_url" placeholder="https://…" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="backfillForm.stage">
            <el-radio value="exported">已导出</el-radio>
            <el-radio value="published">已发布</el-radio>
            <el-radio value="failed">发布失败</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="backfillOpen = false">取消</el-button>
        <el-button type="primary" @click="submitBackfill">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  backfillRecord,
  downloadExport,
  fetchPlatforms,
  fetchRecords,
  runPreflight,
  type PlatformProfile,
  type PreflightReport,
  type PublicationRecord,
} from '@/api/publish'

const route = useRoute()
const novelId = route.params.novelId as string

const platforms = ref<PlatformProfile[]>([])
const selectedPlatform = ref('fanqie')
const report = ref<PreflightReport | null>(null)
const checking = ref(false)
const exporting = ref(false)
const records = ref<PublicationRecord[]>([])
const recordsLoading = ref(false)
const lastRecordId = ref('')

const currentPlatform = computed(() => platforms.value.find((p) => p.key === selectedPlatform.value))

const backfillOpen = ref(false)
const backfillForm = ref<{ id: string; target_book_id: string; target_url: string; stage: string }>({
  id: '',
  target_book_id: '',
  target_url: '',
  stage: 'exported',
})

function stageLabel(stage: string): string {
  return { exported: '已导出', published: '已发布', failed: '失败' }[stage] || stage
}

async function runCheck() {
  checking.value = true
  try {
    report.value = await runPreflight(novelId, selectedPlatform.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '检查失败')
  } finally {
    checking.value = false
  }
}

async function onExport() {
  exporting.value = true
  try {
    lastRecordId.value = await downloadExport(novelId, selectedPlatform.value)
    ElMessage.success('导出成功，已开始下载')
    await loadRecords()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail?.report) {
      report.value = detail.report
      ElMessage.error(detail.message || '质量门禁未通过')
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '导出失败')
    }
  } finally {
    exporting.value = false
  }
}

async function loadRecords() {
  recordsLoading.value = true
  try {
    records.value = await fetchRecords(novelId)
  } finally {
    recordsLoading.value = false
  }
}

function openBackfill(row: PublicationRecord) {
  backfillForm.value = {
    id: row.id,
    target_book_id: row.target_book_id || '',
    target_url: row.target_url || '',
    stage: row.stage || 'exported',
  }
  backfillOpen.value = true
}

async function submitBackfill() {
  await backfillRecord(backfillForm.value.id, {
    target_book_id: backfillForm.value.target_book_id,
    target_url: backfillForm.value.target_url,
    stage: backfillForm.value.stage,
  })
  backfillOpen.value = false
  ElMessage.success('已更新')
  await loadRecords()
}

onMounted(async () => {
  platforms.value = await fetchPlatforms()
  await loadRecords()
})
</script>

<style scoped lang="scss">
.publish-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 14px;
}

.section-hint {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0 0 14px;
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.platform-card {
  border: 1px solid var(--border-default);
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--border-active);
  }

  &.active {
    border-color: var(--accent-ember);
    background: var(--accent-ember-dim);
    box-shadow: var(--accent-ember-glow);
  }

  .platform-name {
    font-family: var(--font-display);
    font-size: 17px;
  }

  .platform-format {
    font-family: var(--font-data);
    font-size: 11px;
    color: var(--text-muted);
    margin: 2px 0 8px;
  }

  .platform-desc {
    font-size: 12px;
    line-height: 1.6;
    color: var(--text-secondary);
    margin: 0 0 8px;
  }

  .platform-link {
    font-size: 12px;
    color: var(--accent-ember);
    text-decoration: none;
  }
}

.report-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.stat {
  background: var(--bg-elevated);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;

  .stat-num {
    font-family: var(--font-data);
    font-size: 20px;
    color: var(--accent-ember);
  }

  .stat-label {
    font-size: 11px;
    color: var(--text-muted);
  }
}

.issue-list {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.8;
}

.last-record {
  margin-left: 12px;
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-data);
}

.muted {
  color: var(--text-muted);
}

.btn-gradient {
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #fff;
  border: none;
}
</style>
