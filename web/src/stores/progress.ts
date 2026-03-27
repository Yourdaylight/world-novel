import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ProgressData, Checkpoint } from '@/api/types'
import { fetchProgress, fetchCheckpoints } from '@/api/progress'

export const useProgressStore = defineStore('progress', () => {
  const completed = ref(0)
  const total = ref(0)
  const phase = ref('idle')
  const paused = ref(false)
  const checkpoints = ref<Checkpoint[]>([])

  const percent = computed(() => (total.value > 0 ? Math.round((completed.value / total.value) * 100) : 0))

  async function loadProgress() {
    const data = await fetchProgress()
    completed.value = data.completed
    total.value = data.total
    phase.value = data.phase
    paused.value = data.paused
  }

  async function loadCheckpoints() {
    const data = await fetchCheckpoints()
    checkpoints.value = data.checkpoints
  }

  function updateFromWS(event: any) {
    if (event.completed !== undefined) completed.value = event.completed
    if (event.total !== undefined) total.value = event.total
    if (event.phase !== undefined) phase.value = event.phase
  }

  return { completed, total, phase, paused, percent, checkpoints, loadProgress, loadCheckpoints, updateFromWS }
})
