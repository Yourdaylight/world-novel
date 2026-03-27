import { computed } from 'vue'
import { useNovelStore } from '@/stores/novel'

/**
 * Returns a computed query params object that includes novel_id if active.
 * Useful for manual API calls that don't go through the axios client.
 */
export function useNovelQuery() {
  const novelStore = useNovelStore()

  const queryParams = computed(() => {
    if (novelStore.activeNovelId) {
      return { novel_id: novelStore.activeNovelId }
    }
    return {}
  })

  return { queryParams, activeNovelId: computed(() => novelStore.activeNovelId) }
}
