import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChapterInfo, ChapterText, ChapterAction } from '@/api/types'
import { fetchChapters, fetchChapterText, fetchChapterActions } from '@/api/chapters'

export const useChapterStore = defineStore('chapters', () => {
  const chapters = ref<ChapterInfo[]>([])
  const activeChapter = ref<number | null>(null)
  const chapterText = ref<ChapterText | null>(null)
  const chapterActions = ref<ChapterAction[]>([])
  const viewMode = ref<'narrative' | 'actions'>('narrative')
  const searchQuery = ref('')
  const loading = ref(false)

  const filteredChapters = computed(() => {
    if (!searchQuery.value) return chapters.value
    const q = searchQuery.value.toLowerCase()
    return chapters.value.filter((_, i) => {
      const title = `第${i + 1}章`
      return title.includes(q) || String(i + 1).includes(q)
    })
  })

  async function loadChapters() {
    loading.value = true
    try {
      const data = await fetchChapters()
      chapters.value = data.chapters
      if (data.chapters.length > 0 && activeChapter.value === null) {
        activeChapter.value = data.chapters[0].chapter_index
      }
    } finally {
      loading.value = false
    }
  }

  async function selectChapter(index: number) {
    activeChapter.value = index
    loading.value = true
    try {
      const [textData, actionData] = await Promise.all([
        fetchChapterText(index),
        fetchChapterActions(index),
      ])
      chapterText.value = textData
      chapterActions.value = actionData.actions
    } finally {
      loading.value = false
    }
  }

  return {
    chapters, activeChapter, chapterText, chapterActions,
    viewMode, searchQuery, filteredChapters, loading,
    loadChapters, selectChapter,
  }
})
