import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AgentFiles } from '@/api/types'
import { fetchAgentFiles, updateAgentSoul } from '@/api/agents'

export const useAgentStore = defineStore('agents', () => {
  const cache = ref<Record<string, AgentFiles>>({})
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

  return { cache, saving, loadFiles, saveSoul }
})
