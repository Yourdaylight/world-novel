import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface AgentAction {
  id: string
  characterName: string
  turnType: string // say, do, think, feel, leave
  content: string
  target?: string
  isVisible: boolean
  timestamp: string
}

export interface AgentStatus {
  characterName: string
  state: 'acting' | 'thinking' | 'waiting' | 'done'
  lastAction?: string
  emotionalDrive?: string
}

export interface ToolCallInfo {
  characterName: string
  toolName: string
  label: string
  timestamp: string
}

export const useLiveMonitorStore = defineStore('liveMonitor', () => {
  // Pipeline state
  const currentPhase = ref('idle')
  const currentChapter = ref(0)
  const currentScene = ref(0)

  // Simulation
  const agentActions = ref<AgentAction[]>([])
  const agentStatuses = ref<Map<string, AgentStatus>>(new Map())
  const toolCalls = ref<ToolCallInfo[]>([])
  const sceneRounds = ref(0)
  const sceneParticipants = ref(new Set<string>())

  // Writing
  const liveText = ref('')
  const liveWordCount = ref(0)

  // Chapter complete
  const chapterCompleted = ref(false)
  const completedChapterTitle = ref('')
  const completedChapterWordCount = ref(0)
  const directorSuggestion = ref('')

  // God decision
  const godDecisionEvents = ref<string[]>([])
  const godDecisionGuidance = ref('')

  // V9: Simulation beat progress (decoupled pipeline)
  const simulationBeatsTotal = ref(0)
  const simulationBeatsCompleted = ref(0)
  const currentBeatId = ref('')
  const isSimulationRunning = ref(false)

  const phaseLabels: Record<string, string> = {
    directing: '导演规划',
    world_building: '构建世界',
    foreshadow_planning: '伏笔网络',
    beat_planning: '节拍规划',
    simulating: '模拟角色场景',
    writing: '撰写章节',
    reviewing: '审校伏笔',
    god_deliberation: '命运裁决',
    god_checkpoint: '命运检查点',
    idle: '待命',
    done: '已完成',
  }

  const phaseLabel = computed(() => phaseLabels[currentPhase.value] || currentPhase.value)

  const isSimulating = computed(() => currentPhase.value === 'simulating')
  const isWriting = computed(() => currentPhase.value === 'writing')
  const isGodDecision = computed(() => currentPhase.value === 'god_deliberation')
  const isIdle = computed(() => currentPhase.value === 'idle' || currentPhase.value === 'done')

  const activeStage = computed(() => {
    if (chapterCompleted.value) return 'chapter_complete'
    if (isSimulating.value) return 'simulating'
    if (isWriting.value) return 'writing'
    if (isGodDecision.value) return 'god_decision'
    return 'waiting'
  })

  // Pipeline structure: preparation (once) + simulation loop (decoupled from writing)
  const preparationSteps = [
    { key: 'directing', label: '导演规划' },
    { key: 'world_building', label: '构建世界' },
    { key: 'foreshadow_planning', label: '伏笔网络' },
    { key: 'beat_planning', label: '节拍规划' },
  ]

  const chapterActivities = [
    { key: 'simulating', label: '模拟', desc: '角色在时间线上自主行动' },
    { key: 'writing', label: '写作', desc: '从时间线编排叙事' },
    { key: 'reviewing', label: '审校', desc: '检查伏笔一致性' },
    { key: 'god_deliberation', label: '命运裁决', desc: '世界事件与指引' },
  ]

  // Keep for backward compat
  const pipelineSteps = [
    ...preparationSteps,
    ...chapterActivities,
  ]

  const isPreparationPhase = computed(() =>
    ['directing', 'world_building', 'foreshadow_planning', 'beat_planning'].includes(currentPhase.value)
  )

  // Track which preparation steps are done
  const completedPreparation = ref(new Set<string>())

  function handlePhaseChange(event: any) {
    const prevPhase = currentPhase.value
    currentPhase.value = event.phase || 'idle'

    // Track preparation phase completion
    if (['directing', 'world_building', 'foreshadow_planning', 'beat_planning'].includes(prevPhase)) {
      completedPreparation.value.add(prevPhase)
    }

    // Reset phase-specific state
    if (event.phase === 'simulating') {
      agentActions.value = []
      agentStatuses.value = new Map()
      toolCalls.value = []
      sceneRounds.value = 0
      sceneParticipants.value = new Set()
    } else if (event.phase === 'writing') {
      liveText.value = ''
      liveWordCount.value = 0
    }
    chapterCompleted.value = false
  }

  function handleAgentTurn(event: any) {
    const action: AgentAction = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      characterName: event.character_name || '未知',
      turnType: event.turn_type || 'say',
      content: event.content || '',
      target: event.target,
      isVisible: event.is_visible !== false,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    }
    agentActions.value.push(action)
    // Keep last 200 actions
    if (agentActions.value.length > 200) {
      agentActions.value = agentActions.value.slice(-200)
    }

    sceneParticipants.value.add(action.characterName)
    sceneRounds.value++

    // Update status
    agentStatuses.value.set(action.characterName, {
      characterName: action.characterName,
      state: 'acting',
      lastAction: action.turnType,
    })
  }

  function handleAgentEvaluate(event: any) {
    const name = event.character_name || '未知'
    agentStatuses.value.set(name, {
      characterName: name,
      state: 'thinking',
      emotionalDrive: event.emotional_drive,
      lastAction: event.approach,
    })
  }

  function handleAgentToolCall(event: any) {
    const toolLabels: Record<string, string> = {
      recall_recent: '回忆近事',
      recall_important: '回忆要事',
      search_memory: '搜索记忆',
      feel_emotions: '感受情绪',
      check_relationship: '审视关系',
      check_all_relationships: '回顾人际',
      review_beliefs: '审视信念',
      recall_deep_memories: '唤起深层记忆',
      check_mental_model: '审视认知',
    }
    const label = toolLabels[event.tool_name] || event.tool_name
    toolCalls.value.push({
      characterName: event.character_name || '未知',
      toolName: event.tool_name,
      label,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    })
    // Keep last 50
    if (toolCalls.value.length > 50) toolCalls.value.shift()
  }

  function handleToken(event: any) {
    const token = event.token || ''
    liveText.value += token
    liveWordCount.value = liveText.value.length
  }

  function handleChapterStart(event: any) {
    currentChapter.value = event.chapter_index ?? currentChapter.value
    liveText.value = ''
    liveWordCount.value = 0
    chapterCompleted.value = false
  }

  function handleChapterCompleted(event: any) {
    chapterCompleted.value = true
    completedChapterTitle.value = event.title || ''
    completedChapterWordCount.value = event.word_count || 0
    currentChapter.value = event.chapter ?? currentChapter.value
  }

  function handleSceneSimulated(event: any) {
    currentScene.value = (event.scene ?? 0) + 1
    sceneRounds.value = event.total_turns || sceneRounds.value
  }

  function handleGodDecision(event: any) {
    godDecisionEvents.value = event.events || []
    godDecisionGuidance.value = event.guidance || ''
  }

  function handleGenerationFinished() {
    currentPhase.value = 'done'
    isSimulationRunning.value = false
  }

  // V9: Decoupled simulation event handlers

  function handlePreparationStarted() {
    reset()
    currentPhase.value = 'directing'
  }

  function handlePreparationFinished(event: any) {
    completedPreparation.value.add('directing')
    completedPreparation.value.add('world_building')
    completedPreparation.value.add('foreshadow_planning')
    completedPreparation.value.add('beat_planning')
    simulationBeatsTotal.value = event.beat_count || 0
  }

  function handleSimulationStarted(event: any) {
    isSimulationRunning.value = true
    simulationBeatsTotal.value = event.beat_count || simulationBeatsTotal.value
    currentPhase.value = 'simulating'
  }

  function handleSimulationFinished(event: any) {
    isSimulationRunning.value = false
    simulationBeatsCompleted.value = event.completed || simulationBeatsCompleted.value
  }

  function handleBeatSimulated(event: any) {
    currentBeatId.value = event.beat_id || ''
    sceneRounds.value = event.total_turns || sceneRounds.value
  }

  function handleSimulationProgress(event: any) {
    if (event.completed !== undefined) simulationBeatsCompleted.value = event.completed
    if (event.total !== undefined) simulationBeatsTotal.value = event.total
  }

  function handleBeatPlanCompleted(event: any) {
    simulationBeatsTotal.value = event.beat_count || 0
    completedPreparation.value.add('beat_planning')
  }

  function reset() {
    currentPhase.value = 'idle'
    currentChapter.value = 0
    currentScene.value = 0
    agentActions.value = []
    agentStatuses.value = new Map()
    toolCalls.value = []
    sceneRounds.value = 0
    sceneParticipants.value = new Set()
    liveText.value = ''
    liveWordCount.value = 0
    chapterCompleted.value = false
    completedChapterTitle.value = ''
    completedChapterWordCount.value = 0
    godDecisionEvents.value = []
    godDecisionGuidance.value = ''
    completedPreparation.value = new Set()
    simulationBeatsTotal.value = 0
    simulationBeatsCompleted.value = 0
    currentBeatId.value = ''
    isSimulationRunning.value = false
  }

  return {
    currentPhase, currentChapter, currentScene,
    agentActions, agentStatuses, toolCalls,
    sceneRounds, sceneParticipants,
    liveText, liveWordCount,
    chapterCompleted, completedChapterTitle, completedChapterWordCount, directorSuggestion,
    godDecisionEvents, godDecisionGuidance,
    simulationBeatsTotal, simulationBeatsCompleted, currentBeatId, isSimulationRunning,
    phaseLabel, isSimulating, isWriting, isGodDecision, isIdle, activeStage,
    pipelineSteps, preparationSteps, chapterActivities,
    isPreparationPhase, completedPreparation,
    handlePhaseChange, handleAgentTurn, handleAgentEvaluate, handleAgentToolCall,
    handleToken, handleChapterStart, handleChapterCompleted, handleSceneSimulated,
    handleGodDecision, handleGenerationFinished, reset,
    handlePreparationStarted, handlePreparationFinished,
    handleSimulationStarted, handleSimulationFinished,
    handleBeatSimulated, handleSimulationProgress, handleBeatPlanCompleted,
  }
})
