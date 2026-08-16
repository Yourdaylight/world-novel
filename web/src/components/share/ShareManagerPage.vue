<template>
  <div class="share-page page-container">
    <header class="page-header">
      <div class="header-title">
        <h1 class="page-title">分享与公开阅读</h1>
        <p class="page-subtitle">
          生成公开链接分享给读者：匿名可试读，注册后可读全书。你可以随时关闭分享或调整试读范围。
        </p>
      </div>
      <div class="header-actions">
        <el-button v-if="!share" type="primary" @click="onCreate" :loading="creating">
          创建分享链接
        </el-button>
      </div>
    </header>

    <div v-if="loading" class="loading-row">加载中…</div>

    <el-empty v-else-if="!share" description="还没有分享链接" />

    <template v-else>
      <!-- 链接卡片 -->
      <section class="card">
        <div class="link-row">
          <div class="link-info">
            <div class="link-label">
              公开阅读地址
              <el-tag :type="share.status === 'active' ? 'success' : 'info'" size="small">
                {{ share.status === 'active' ? '分享中' : '已关闭' }}
              </el-tag>
            </div>
            <div class="link-url">{{ share.share_url }}</div>
          </div>
          <div class="link-actions">
            <el-button @click="copyLink">复制链接</el-button>
            <el-button
              :type="share.status === 'active' ? 'danger' : 'success'"
              plain
              @click="toggleStatus"
            >
              {{ share.status === 'active' ? '关闭分享' : '重新开启' }}
            </el-button>
          </div>
        </div>

        <div class="stat-row">
          <div class="stat"><b>{{ share.view_count }}</b><span>浏览</span></div>
          <div class="stat"><b>{{ share.read_count }}</b><span>章节阅读</span></div>
          <div class="stat"><b>{{ share.chapter_count }}</b><span>章节</span></div>
          <div class="stat"><b>{{ share.word_count.toLocaleString() }}</b><span>总字数</span></div>
        </div>
      </section>

      <!-- 试读策略 -->
      <section class="card">
        <h2 class="section-title">试读策略</h2>
        <el-form label-width="120px" class="trial-form" @submit.prevent>
          <el-form-item label="试读模式">
            <el-radio-group v-model="trialMode" @change="saveTrial">
              <el-radio value="first_n_chapters">前 N 章</el-radio>
              <el-radio value="word_count">按累计字数</el-radio>
              <el-radio value="ratio">按全书比例</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="trialValueLabel">
            <el-input-number
              v-model="trialValue"
              :min="0"
              :max="trialMode === 'ratio' ? 100 : 10000"
              @change="saveTrial"
            />
            <span class="trial-hint">{{ trialHint }}</span>
          </el-form-item>
        </el-form>
        <p class="section-hint">
          策略变更对匿名读者即时生效；注册用户不受试读限制（开源版注册即全文，付费会员为商业版预留）。
        </p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createShare, fetchMyShares, updateShare, type ShareLink, type TrialMode } from '@/api/share'

const route = useRoute()
const novelId = route.params.novelId as string

const loading = ref(true)
const creating = ref(false)
const share = ref<ShareLink | null>(null)
const trialMode = ref<TrialMode>('first_n_chapters')
const trialValue = ref(3)

const trialValueLabel = computed(() => {
  if (trialMode.value === 'first_n_chapters') return '可试读章节数'
  if (trialMode.value === 'word_count') return '可试读累计字数'
  return '可试读比例 (%)'
})

const trialHint = computed(() => {
  if (trialMode.value === 'first_n_chapters') return `匿名读者可读前 ${trialValue.value} 章`
  if (trialMode.value === 'word_count') return `匿名读者累计可读约 ${trialValue.value} 字`
  return `匿名读者可读约 ${trialMode.value ? Math.floor((share.value?.chapter_count || 0) * trialValue.value / 100) : 0} 章`
})

async function load() {
  loading.value = true
  try {
    const shares = await fetchMyShares()
    share.value = shares.find((s) => s.novel_id === novelId) || shares[0] || null
    if (share.value) {
      trialMode.value = share.value.trial_mode
      trialValue.value = share.value.trial_value
    }
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  creating.value = true
  try {
    share.value = await createShare(novelId, trialMode.value, trialValue.value)
    ElMessage.success('分享链接已创建')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function copyLink() {
  if (!share.value?.share_url) return
  await navigator.clipboard.writeText(share.value.share_url)
  ElMessage.success('链接已复制')
}

async function saveTrial() {
  if (!share.value) return
  try {
    share.value = await updateShare(share.value.id, {
      trial_mode: trialMode.value,
      trial_value: trialValue.value,
    })
    ElMessage.success('试读策略已更新（即时生效）')
  } catch (e: any) {
    ElMessage.error('更新失败')
  }
}

async function toggleStatus() {
  if (!share.value) return
  const next = share.value.status === 'active' ? 'disabled' : 'active'
  share.value = await updateShare(share.value.id, { status: next })
  ElMessage.success(next === 'disabled' ? '分享已关闭，所有公开链接立即失效' : '分享已重新开启')
}

onMounted(load)
</script>

<style scoped lang="scss">
.share-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.loading-row {
  color: var(--text-muted);
  padding: 40px;
  text-align: center;
}

.link-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.link-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.link-url {
  font-family: var(--font-data);
  font-size: 14px;
  color: var(--accent-ember);
  word-break: break-all;
}

.link-actions {
  display: flex;
  gap: 8px;
}

.stat-row {
  display: flex;
  gap: 24px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border-muted);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;

  b {
    font-family: var(--font-data);
    font-size: 20px;
    color: var(--accent-ember);
  }

  span {
    font-size: 11px;
    color: var(--text-muted);
  }
}

.section-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 16px;
}

.section-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 8px 0 0;
}

.trial-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
