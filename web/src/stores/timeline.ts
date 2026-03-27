import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TimelineEra, TimelineEvent, GodDecision } from '@/api/types'
import { fetchTimeline, fetchGodDecisions } from '@/api/timeline'

export const useTimelineStore = defineStore('timeline', () => {
  const eras = ref<TimelineEra[]>([])
  const events = ref<TimelineEvent[]>([])
  const decisions = ref<GodDecision[]>([])
  const loading = ref(false)

  async function loadAll() {
    loading.value = true
    try {
      const [tRes, dRes] = await Promise.all([fetchTimeline(), fetchGodDecisions()])
      eras.value = tRes.eras
      events.value = tRes.events
      decisions.value = dRes.decisions
    } finally {
      loading.value = false
    }
  }

  return { eras, events, decisions, loading, loadAll }
})
