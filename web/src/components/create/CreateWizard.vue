<template>
  <div class="create-wizard">
    <header class="wizard-header">
      <button class="back-btn" @click="router.push('/')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回首页
      </button>
      <h1 class="wizard-title">创建新世界</h1>
    </header>

    <div class="wizard-steps-wrap">
      <el-steps :active="currentStep" finish-status="success" align-center>
        <el-step title="世界本质" description="这个世界是什么" />
        <el-step title="世界起源" description="从何而来" />
        <el-step title="世界命运" description="往何处去" />
        <el-step title="基础参数" description="设定细节" />
      </el-steps>
    </div>

    <div class="wizard-body">
      <!-- Step 1-3: Propositions -->
      <template v-if="currentStep < 3">
        <div class="proposition-layout">
          <div class="prop-main">
            <StepProposition
              :step="currentStep + 1"
              :title="stepTitles[currentStep]"
              :guide="stepGuides[currentStep]"
              :examples="stepExamples[currentStep]"
              v-model="propositions[stepKeys[currentStep]]"
            />
          </div>
          <div class="prop-aside">
            <AiFeedback
              :step="currentStep + 1"
              :text="propositions[stepKeys[currentStep]]"
              :context="currentContext"
            />
          </div>
        </div>
      </template>

      <!-- Step 4: Parameters -->
      <template v-else>
        <div class="params-panel">
          <StepParams
            v-model:title="form.title"
            v-model:genre="form.genre"
            v-model:num-chapters="form.numChapters"
            v-model:num-characters="form.numCharacters"
            :loading="creating"
          />
        </div>
      </template>
    </div>

    <div class="wizard-footer">
      <button
        v-if="currentStep > 0"
        class="footer-btn footer-btn-outline"
        @click="currentStep--"
      >
        上一步
      </button>
      <button
        v-if="currentStep < 3"
        class="footer-btn footer-btn-primary"
        :disabled="!canProceed"
        @click="currentStep++"
      >
        下一步
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6"/></svg>
      </button>
      <button
        v-if="currentStep === 3"
        class="footer-btn footer-btn-create"
        :disabled="!form.title || creating"
        @click="onCreateWorld"
      >
        <svg v-if="creating" class="spin-icon" width="15" height="15" viewBox="0 0 50 50"><circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="4" stroke-dasharray="80, 200" stroke-linecap="round"/></svg>
        <template v-else>开始创世</template>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useNovelStore } from '@/stores/novel'
import StepProposition from './StepProposition.vue'
import StepParams from './StepParams.vue'
import AiFeedback from './AiFeedback.vue'

const router = useRouter()
const novelStore = useNovelStore()

const currentStep = ref(0)
const creating = ref(false)

const propositions = reactive({
  what_is: '',
  where_from: '',
  where_to: '',
})

const form = reactive({
  title: '',
  genre: '玄幻',
  numChapters: 5,
  numCharacters: 5,
})

const stepKeys = ['what_is', 'where_from', 'where_to'] as const
const stepTitles = ['这个世界是什么？', '从何而来？', '往何处去？']
const stepGuides = [
  '描述你想创造的世界的本质。它是一个什么样的世界？有什么独特之处？',
  '这个世界的起源是什么？它是如何诞生的？其中蕴含什么样的初始矛盾？',
  '这个世界将走向何方？它的终极命运是什么？人们在追求什么？',
]
const stepExamples: string[][] = [
  [
    '一个力量来源于情感共鸣的武侠世界，每个人的武功与内心情感紧密相连',
    '一个被永恒黑暗笼罩的末日世界，光明成为最稀缺的资源',
    '一个意识可以自由穿梭于不同时间线的科幻世界',
  ],
  [
    '世界诞生于一位远古神明的最后一滴眼泪，泪水中蕴含着创世与毁灭的双重力量',
    '文明源于一次星际殖民船的坠毁，幸存者在荒芜星球上重建社会',
    '所有历史都始于一个谎言——上古英雄的"伟大功绩"其实是最大的骗局',
  ],
  [
    '世界正在缓慢崩塌，唯一的拯救方式需要牺牲所有人最珍贵的记忆',
    '两个对立的文明必须融合，但融合意味着双方都将失去自己的身份',
    '最终的真相是：这个世界本身就是某个更高维度存在的梦境',
  ],
]

const canProceed = computed(() => {
  const key = stepKeys[currentStep.value]
  return key ? propositions[key].trim().length > 10 : true
})

const currentContext = computed(() => {
  const ctx: Record<string, string> = {}
  if (currentStep.value >= 1) ctx.what_is = propositions.what_is
  if (currentStep.value >= 2) ctx.where_from = propositions.where_from
  return ctx
})

async function onCreateWorld() {
  if (!form.title.trim()) {
    ElMessage.warning('请输入小说标题')
    return
  }

  creating.value = true
  try {
    const res = await novelStore.createWorld({
      title: form.title,
      genre: form.genre,
      propositions: {
        what_is: propositions.what_is,
        where_from: propositions.where_from,
        where_to: propositions.where_to,
      },
      num_chapters: form.numChapters,
      num_characters: form.numCharacters,
    })

    if (res.ok && res.novel_id) {
      ElMessage.success('世界创建成功！')
      router.push(`/world/${res.novel_id}/overview`)
    } else {
      ElMessage.error(res.error || '创建失败')
    }
  } finally {
    creating.value = false
  }
}
</script>

<style scoped lang="scss">
.create-wizard {
  min-height: 100vh;
  background: var(--bg-gradient);
  padding: var(--sp-xl);
  max-width: 1000px;
  margin: 0 auto;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: var(--bg-noise);
    pointer-events: none;
    opacity: 0.4;
  }
}

/* === Header === */
.wizard-header {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
  padding-bottom: var(--sp-md);
  border-bottom: 1px solid var(--border-default);
  position: relative;
  z-index: 1;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 500;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  transition: all var(--duration-base) ease;

  &:hover {
    color: var(--text-primary);
    background: var(--bg-elevated);
  }
}

.wizard-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

/* === Steps === */
.wizard-steps-wrap {
  position: relative;
  z-index: 1;
  margin-bottom: var(--sp-xl);

  .el-steps {
    max-width: 600px;
    margin: 0 auto;
  }
}

/* === Body === */
.wizard-body {
  position: relative;
  z-index: 1;
  min-height: 420px;
  margin-bottom: var(--sp-xl);
}

.proposition-layout {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: var(--sp-xl);
  align-items: start;
}

.prop-main {
  min-width: 0;
}

.prop-aside {
  position: sticky;
  top: calc(var(--sp-xl) + 16px);
}

.params-panel {
  max-width: 640px;
  margin: 0 auto;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: var(--sp-xl);
  box-shadow: var(--shadow-md);
}

/* === Footer === */
.wizard-footer {
  display: flex;
  justify-content: center;
  gap: var(--sp-sm);
  padding-top: var(--sp-xl);
  border-top: 1px solid var(--border-default);
  position: relative;
  z-index: 1;
}

.footer-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 11px 28px;
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--duration-base) ease;
  letter-spacing: 0.01em;

  &.footer-btn-primary {
    background: linear-gradient(135deg, #d97706, #b45309);
    color: #fff;
    border: none;
    box-shadow: 0 2px 10px rgba(217,119,6,0.28);

    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 6px 18px rgba(217,119,6,0.38);
    }
  }

  &.footer-btn-create {
    background: linear-gradient(135deg, #d97706, #b45309, #92400e);
    color: #fff;
    border: none;
    padding: 12px 40px;
    font-size: var(--fs-base);
    box-shadow: 0 3px 14px rgba(217,119,6,0.32);

    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 8px 26px rgba(217,119,6,0.42);
    }
  }

  &.footer-btn-outline {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border-default);

    &:hover {
      color: var(--text-primary);
      border-color: var(--text-muted);
      background: var(--bg-elevated);
    }
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
