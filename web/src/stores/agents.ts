import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AgentFiles } from '@/api/types'
import { fetchAgentFiles, updateAgentSoul } from '@/api/agents'
import {
  fetchSkills,
  createSkill,
  updateSkill,
  deleteSkill,
  toggleSkill,
  type CharacterSkill,
} from '@/api/agents'

export const useAgentStore = defineStore('agents', () => {
  const cache = ref<Record<string, AgentFiles>>({})
  const skillsCache = ref<Record<string, CharacterSkill[]>>({})
  const saving = ref(false)

  async function loadFiles(characterId: string) {
    const data = await fetchAgentFiles(characterId)
    cache.value[characterId] = data
    return data
  }

  async function saveSoul(characterId: string, content: string) {
    saving.value = true
    try {
      const res = await updateAgentSoul(characterId, content)
      if (res.ok && cache.value[characterId]) {
        cache.value[characterId].soul_md = content
      }
      return res
    } finally {
      saving.value = false
    }
  }

  // ── Skills ──────────────────────────────────────────

  async function loadSkills(characterId: string) {
    const res = await fetchSkills(characterId)
    if (res.ok) {
      skillsCache.value[characterId] = res.skills || []
    }
    return res
  }

  async function addSkill(characterId: string, payload: Partial<CharacterSkill>) {
    const res = await createSkill(characterId, payload)
    if (res.ok) {
      await loadSkills(characterId)
    }
    return res
  }

  async function editSkill(characterId: string, skillId: string, payload: Partial<CharacterSkill>) {
    const res = await updateSkill(characterId, skillId, payload)
    if (res.ok) {
      await loadSkills(characterId)
    }
    return res
  }

  async function removeSkill(characterId: string, skillId: string) {
    const res = await deleteSkill(characterId, skillId)
    if (res.ok) {
      skillsCache.value[characterId] = (skillsCache.value[characterId] || []).filter(
        (s) => s.skill_id !== skillId,
      )
    }
    return res
  }

  async function toggle(characterId: string, skillId: string, enabled: boolean) {
    const res = await toggleSkill(characterId, skillId, enabled)
    if (res.ok) {
      const list = skillsCache.value[characterId] || []
      const idx = list.findIndex((s) => s.skill_id === skillId)
      if (idx >= 0) list[idx].enabled = enabled
    }
    return res
  }

  return {
    cache,
    skillsCache,
    saving,
    loadFiles,
    saveSoul,
    loadSkills,
    addSkill,
    editSkill,
    removeSkill,
    toggle,
  }
})
