import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Character, RelationshipEdge, EmotionState } from '@/api/types'
import { fetchStory, fetchRelationships } from '@/api/story'
import client from '@/api/client'

export const useCharacterStore = defineStore('characters', () => {
  const characters = ref<Character[]>([])
  const edges = ref<RelationshipEdge[]>([])
  const loading = ref(false)
  const emotionCache = ref<Record<string, EmotionState[]>>({})

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

  return { characters, edges, loading, emotionCache, loadCharacters, loadEmotions }
})
