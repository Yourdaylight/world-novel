<template>
  <div class="skills-manager">
    <div class="skills-header">
      <span class="panel-title">⚡ 技能与行为模式</span>
      <el-button type="primary" size="small" @click="openCreate">
        ＋ 新增技能
      </el-button>
    </div>

    <p class="skills-tip">
      技能是角色演化的第三根杠杆：定义角色擅长什么、如何行事、向哪成长。
      启用后会在场景决策中自动注入，引导角色行为与演化方向。
    </p>

    <div v-loading="loading" class="skills-list">
      <el-empty v-if="!loading && !skills.length" description="暂无技能，点击「新增技能」创建第一个" :image-size="60" />

      <div v-for="skill in sortedSkills" :key="skill.skill_id" class="skill-card" :class="{ disabled: !skill.enabled }">
        <div class="skill-card-top">
          <div class="skill-name-row">
            <el-tag size="small" :type="categoryType(skill.category)" effect="dark">
              {{ categoryLabel(skill.category) }}
            </el-tag>
            <span class="skill-name">{{ skill.name }}</span>
            <span v-if="skill.category === 'ability'" class="skill-level">
              熟练度 {{ Math.round(skill.level * 100) }}
            </span>
          </div>
          <div class="skill-actions">
            <el-switch
              :model-value="skill.enabled"
              size="small"
              @change="(v: any) => onToggle(skill, !!v)"
            />
            <el-button link type="primary" size="small" @click="openEdit(skill)">编辑</el-button>
            <el-popconfirm title="确定删除该技能？" @confirm="onDelete(skill)">
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>

        <p v-if="skill.description" class="skill-desc">{{ skill.description }}</p>
        <p v-if="skill.trigger_conditions" class="skill-trigger">
          <span class="label">触发：</span>{{ skill.trigger_conditions }}
        </p>
        <p v-if="skill.category === 'growth' && skill.direction" class="skill-direction">
          <span class="label">成长方向：</span>{{ skill.direction }}
        </p>
      </div>
    </div>

    <!-- 新增/编辑 Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? `编辑技能 — ${editing.name}` : '新增技能'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" label-position="left">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：剑术 / 谨慎 / 侠义之心" />
        </el-form-item>

        <el-form-item label="类型">
          <el-radio-group v-model="form.category">
            <el-radio-button value="ability">专长</el-radio-button>
            <el-radio-button value="habit">行为模式</el-radio-button>
            <el-radio-button value="growth">演化方向</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="行为描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="角色如何使用这项技能 / 表现出什么行为倾向"
          />
        </el-form-item>

        <el-form-item label="触发条件">
          <el-input v-model="form.trigger_conditions" placeholder="什么情境下会动用（可选）" />
        </el-form-item>

        <el-form-item v-if="form.category === 'ability'" label="熟练度">
          <el-slider v-model="form.level" :min="0" :max="1" :step="0.1" show-input :show-input-controls="false" />
        </el-form-item>

        <el-form-item v-if="form.category === 'growth'" label="成长方向">
          <el-input
            v-model="form.direction"
            type="textarea"
            :rows="2"
            placeholder="该技能如何塑造成长？如：从独行侠成长为守护一方的大侠"
          />
        </el-form-item>

        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="99" />
          <span class="priority-tip">数值越大越靠前</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '@/stores/agents'
import type { CharacterSkill } from '@/api/agents'

const props = defineProps<{
  characterId: string
  characterName: string
  visible: boolean
}>()

const agentStore = useAgentStore()
const skills = ref<CharacterSkill[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editing = ref<CharacterSkill | null>(null)

const emptyForm = () => ({
  name: '',
  category: 'ability',
  description: '',
  trigger_conditions: '',
  level: 0.5,
  direction: '',
  enabled: true,
  priority: 0,
})

const form = ref(emptyForm())

const sortedSkills = computed(() => {
  return [...skills.value].sort((a, b) => b.priority - a.priority)
})

function categoryLabel(cat: string): string {
  return { ability: '专长', habit: '行为模式', growth: '演化方向' }[cat] || cat
}

function categoryType(cat: string): 'primary' | 'success' | 'warning' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info'> = {
    ability: 'primary',
    habit: 'warning',
    growth: 'success',
  }
  return map[cat] || 'info'
}

watch(() => props.visible, async (val) => {
  if (val && props.characterId) {
    await load()
  }
})

async function load() {
  loading.value = true
  try {
    const res = await agentStore.loadSkills(props.characterId)
    skills.value = res.ok ? (res.skills || []) : []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(skill: CharacterSkill) {
  editing.value = skill
  form.value = {
    name: skill.name,
    category: skill.category,
    description: skill.description,
    trigger_conditions: skill.trigger_conditions,
    level: skill.level,
    direction: skill.direction,
    enabled: skill.enabled,
    priority: skill.priority,
  }
  dialogVisible.value = true
}

async function onSave() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写技能名称')
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value }
    if (editing.value) {
      const res = await agentStore.editSkill(props.characterId, editing.value.skill_id, payload)
      if (!res.ok) { ElMessage.error(res.error || '保存失败'); return }
      ElMessage.success('技能已更新')
    } else {
      const res = await agentStore.addSkill(props.characterId, payload)
      if (!res.ok) { ElMessage.error(res.error || '创建失败'); return }
      ElMessage.success('技能已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function onToggle(skill: CharacterSkill, enabled: boolean) {
  const res = await agentStore.toggle(props.characterId, skill.skill_id, enabled)
  if (!res.ok) {
    ElMessage.error(res.error || '操作失败')
    return
  }
  ElMessage.success(enabled ? '已启用' : '已停用')
}

async function onDelete(skill: CharacterSkill) {
  const res = await agentStore.removeSkill(props.characterId, skill.skill_id)
  if (!res.ok) { ElMessage.error(res.error || '删除失败'); return }
  ElMessage.success('技能已删除')
  await load()
}
</script>

<style scoped lang="scss">
.skills-manager {
  padding: 4px 0;
}

.skills-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.panel-title {
  font-weight: 600;
  font-size: 15px;
}

.skills-tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
  margin: 0 0 12px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.skills-list {
  min-height: 80px;
}

.skill-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 10px;
  transition: opacity 0.2s;

  &.disabled {
    opacity: 0.55;
  }
}

.skill-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.skill-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.skill-name {
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.skill-level {
  font-size: 12px;
  color: var(--el-color-primary);
}

.skill-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.skill-desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
}

.skill-trigger,
.skill-direction {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);

  .label {
    color: var(--el-text-color-regular);
    font-weight: 500;
  }
}

.priority-tip {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
