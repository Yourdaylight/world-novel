import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLiveWritingStore = defineStore('liveWriting', () => {
  const currentPhase = ref('')
  const currentChapter = ref<number | null>(null)
  const tokens = ref<string[]>([])
  const liveText = ref('')
  const isWriting = ref(false)

  function handleEvent(event: any) {
    switch (event.type) {
      case 'phase_change':
        currentPhase.value = event.phase || ''
        break
      case 'chapter_start':
        currentChapter.value = event.chapter_index ?? null
        tokens.value = []
        liveText.value = ''
        isWriting.value = true
        break
      case 'token':
        tokens.value.push(event.token || '')
        liveText.value += event.token || ''
        break
      case 'chapter_done':
        isWriting.value = false
        break
    }
  }

  function reset() {
    currentPhase.value = ''
    currentChapter.value = null
    tokens.value = []
    liveText.value = ''
    isWriting.value = false
  }

  return { currentPhase, currentChapter, tokens, liveText, isWriting, handleEvent, reset }
})
