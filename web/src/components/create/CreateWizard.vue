<template>
  <div class="create-wizard">
    <header class="wizard-header">
      <el-button text @click="router.push('/')">← 返回首页</el-button>
      <h1>🌍 创建新世界</h1>
    </header>

    <el-steps :active="currentStep" finish-status="success" align-center class="wizard-steps">
      <el-step title="世界本质" description="这个世界是什么" />
      <el-step title="世界起源" description="从何而来" />
      <el-step title="世界命运" description="往何处去" />
      <el-step title="基础参数" description="设定细节" />
    </el-steps>

    <div class="wizard-body">
      <!-- Step 1-3: Propositions -->
      <template v-if="currentStep < 3">
        <el-row :gutter="24">
          <el-col :span="14">
            <StepProposition
              :step="currentStep + 1"
              :title="stepTitles[currentStep]"
              :guide="stepGuides[currentStep]"
              :examples="stepExamples[currentStep]"
              v-model="propositions[stepKeys[currentStep]]"
            />
          </el-col>
          <el-col :span="10">
            <AiFeedback
              :step="currentStep + 1"
              :text="propositions[stepKeys[currentStep]]"
              :context="currentContext"
            />
          </el-col>
        </el-row>
      </template>

      <!-- Step 4: Parameters -->
      <template v-else>
        <StepParams
          v-model:title="form.title"
          v-model:genre="form.genre"
          v-model:num-chapters="form.numChapters"
          v-model:num-characters="form.numCharacters"
          :loading="creating"
        />
      </template>
    </div>

    <div class="wizard-footer">
      <el-button v-if="currentStep > 0" @click="currentStep--">上一步</el-button>
      <el-button
        v-if="currentStep < 3"
        type="primary"
        :disabled="!canProceed"
        @click="currentStep++"
      >
        下一步
      </el-button>
      <el-button
        v-if="currentStep === 3"
        type="primary"
        size="large"
        :loading="creating"
        :disabled="!form.title"
        @click="onCreateWorld"
      >
        🌟 开始创世
      </el-button>
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
  background: var(--bg-primary, #0f0f23);
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.wizard-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;

  h1 {
    font-size: 1.5rem;
    color: var(--text-primary, #e0e0ff);
    margin: 0;
  }
}

.wizard-steps {
  margin-bottom: 2rem;
}

.wizard-body {
  min-height: 400px;
  margin-bottom: 2rem;
}

.wizard-footer {
  display: flex;
  justify-content: center;
  gap: 1rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border, #2a2a4a);
}
</style>
