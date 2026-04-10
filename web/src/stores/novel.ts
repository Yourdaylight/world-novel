import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { NovelInfo, CreateWorldRequest } from '@/api/types'
import { fetchNovels, selectNovel, createWorld as apiCreateWorld, deleteWorld as apiDeleteWorld } from '@/api/novels'

export const useNovelStore = defineStore('novel', () => {
  const novels = ref<NovelInfo[]>([])
  const activeNovelId = ref<string | null>(null)
  const loading = ref(false)

  async function loadNovels() {
    loading.value = true
    try {
      const data = await fetchNovels()
      novels.value = data.novels
      activeNovelId.value = data.active_novel_id
    } catch (e) {
      console.error('Failed to load novels:', e)
    } finally {
      loading.value = false
    }
  }

  async function switchNovel(novelId: string) {
    try {
      const res = await selectNovel(novelId)
      if (res.ok) {
        activeNovelId.value = res.active_novel_id ?? novelId
      } else {
        console.warn('Switch novel failed:', res)
      }
    } catch (e) {
      console.error('Switch novel error:', e)
    }
  }

  async function createWorld(req: CreateWorldRequest) {
    const res = await apiCreateWorld(req)
    if (res.ok && res.novel_id) {
      activeNovelId.value = res.novel_id
      await loadNovels()
    }
    return res
  }

  async function removeWorld(novelId: string) {
    const res = await apiDeleteWorld(novelId)
    if (res.ok) {
      await loadNovels()
    }
    return res
  }

  return { novels, activeNovelId, loading, loadNovels, switchNovel, createWorld, removeWorld }
})
