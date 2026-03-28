import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface LogEntry {
  time: string
  text: string
  type: string
}

const phaseLabels: Record<string, string> = {
  directing: '导演规划 — 分析命题、设计冲突弧线',
  world_building: '构建世界 — 生成地理、势力、魔法体系',
  foreshadow_planning: '伏笔网络 — 规划植入点和回收时机',
  simulating: '模拟角色场景',
  writing: '撰写章节',
  reviewing: '审校伏笔',
  god_deliberation: '命运裁决',
}

export const useEventLogStore = defineStore('eventLog', () => {
  const entries = ref<LogEntry[]>([])
  const maxEntries = 100

  function addEntry(text: string, type: string = 'info') {
    const now = new Date()
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
    entries.value.push({ time, text, type })
    if (entries.value.length > maxEntries) entries.value.shift()
  }

  function clear() {
    entries.value = []
  }

  function pushFromWS(event: any) {
    const t = event.type
    if (t === 'phase_change') {
      const label = phaseLabels[event.phase] || event.phase
      addEntry(`阶段切换: ${label}`, 'phase')
    } else if (t === 'scene_simulated') {
      addEntry(`场景模拟完成: 第${event.chapter + 1}章 场景${event.scene + 1} (${event.action_count}个行动)`, 'scene')
    } else if (t === 'scene_written') {
      addEntry(`场景写作完成: 第${event.chapter + 1}章 场景${event.scene + 1} (${event.word_count}字)`, 'write')
    } else if (t === 'chapter_completed') {
      addEntry(`第${event.chapter + 1}章完成: ${event.title} (${event.word_count}字)`, 'chapter')
    } else if (t === 'god_decision') {
      const events = event.events?.join('、') || ''
      addEntry(`命运裁决: ${events} ${event.guidance?.substring(0, 60) || ''}`, 'god')
    } else if (t === 'checkpoint_saved') {
      addEntry(`检查点已保存 (${event.chapters_completed}章完成)`, 'checkpoint')
    } else if (t === 'generation_started') {
      addEntry('生成流程已启动', 'start')
    } else if (t === 'generation_finished') {
      addEntry(`生成完成 — ${event.status}`, 'done')
    } else if (t === 'generation_error') {
      addEntry(`生成出错: ${event.error}`, 'error')
    } else if (t === 'novel_completed') {
      addEntry(`小说完成: ${event.title} (${event.word_count}字, ${event.total_chapters}章)`, 'done')
    }
  }

  return { entries, addEntry, clear, pushFromWS }
})
