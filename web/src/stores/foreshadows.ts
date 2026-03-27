import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Foreshadow, PlotThread } from '@/api/types'
import { fetchForeshadows, fetchPlotThreads } from '@/api/foreshadows'

export const useForeshadowStore = defineStore('foreshadows', () => {
  const foreshadows = ref<Foreshadow[]>([])
  const plotThreads = ref<PlotThread[]>([])
  const loading = ref(false)

  async function loadAll() {
    loading.value = true
    try {
      const [fRes, pRes] = await Promise.all([fetchForeshadows(), fetchPlotThreads()])
      foreshadows.value = fRes.foreshadows
      plotThreads.value = pRes.plot_threads
    } finally {
      loading.value = false
    }
  }

  return { foreshadows, plotThreads, loading, loadAll }
})
