import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { WorldData, OutlineData, Volume } from '@/api/types'
import { fetchWorld, fetchOutline } from '@/api/world'

export const useWorldStore = defineStore('world', () => {
  const world = ref<WorldData | null>(null)
  const outline = ref<OutlineData | null>(null)
  const volumes = ref<Volume[]>([])
  const loading = ref(false)

  async function loadWorld() {
    loading.value = true
    try {
      const [worldRes, outlineRes] = await Promise.all([fetchWorld(), fetchOutline()])
      world.value = worldRes.world
      outline.value = outlineRes.outline
      volumes.value = outlineRes.volumes
    } finally {
      loading.value = false
    }
  }

  return { world, outline, volumes, loading, loadWorld }
})
