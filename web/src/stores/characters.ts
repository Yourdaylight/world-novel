import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Character, RelationshipEdge, EmotionState, GraphData } from '@/api/types'
import { fetchStory, fetchRelationships, fetchGraphData } from '@/api/story'
import client from '@/api/client'

export const useCharacterStore = defineStore('characters', () => {
  const characters = ref<Character[]>([])
  const edges = ref<RelationshipEdge[]>([])
  const loading = ref(false)
  const emotionCache = ref<Record<string, EmotionState[]>>({})

  // V10: Graph data from Neo4j
  const graphData = ref<GraphData | null>(null)
  const graphLoading = ref(false)

  async function loadCharacters() {
    loading.value = true
    try {
      const [storyRes, relRes] = await Promise.all([fetchStory(), fetchRelationships()])
      characters.value = storyRes.characters
      edges.value = relRes.edges
    } finally {
      loading.value = false
    }
  }

  async function loadEmotions(characterId: string) {
    if (emotionCache.value[characterId]) return emotionCache.value[characterId]
    const { data } = await client.get(`/emotions/${characterId}`)
    emotionCache.value[characterId] = data.states || []
    return emotionCache.value[characterId]
  }

  async function loadGraphData() {
    graphLoading.value = true
    try {
      graphData.value = await fetchGraphData()
    } catch {
      graphData.value = null
    } finally {
      graphLoading.value = false
    }
  }

  return {
    characters, edges, loading, emotionCache,
    graphData, graphLoading,
    loadCharacters, loadEmotions, loadGraphData,
  }
})
