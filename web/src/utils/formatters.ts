export function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function formatPhase(phase: string): string {
  const map: Record<string, string> = {
    idle: '空闲',
    directing: '导演规划',
    world_building: '世界观构建',
    foreshadow_planning: '伏笔规划',
    simulating: '场景模拟',
    writing: '正在创作',
    reviewing: '审校中',
    god_deliberation: '命运裁决',
    outline: '大纲规划',
    review: '审阅修订',
    done: '已完成',
    error: '错误',
  }
  return map[phase] || phase
}

export function truncate(text: string, max: number = 100): string {
  if (!text || text.length <= max) return text
  return text.slice(0, max) + '…'
}

/** 角色类型英文→中文映射 */
export function formatRole(role: string): string {
  const map: Record<string, string> = {
    protagonist: '主角',
    antagonist: '反派',
    deuteragonist: '女主',
    mentor: '导师',
    sidekick: '伙伴',
    love_interest: '恋人',
    rival: '宿敌',
    comic_relief: '谐星',
    supporting: '配角',
    ' protagonist': '主角',
  }
  const trimmed = role.trim().toLowerCase()
  return map[trimmed] || role.trim()
}

/** 行动类型英文→中文映射 */
export function formatActionType(type: string): string {
  const map: Record<string, string> = {
    dialogue: '对话',
    thought: '内心',
    behavior: '行动',
    reaction: '反应',
  }
  return map[type] || type
}
