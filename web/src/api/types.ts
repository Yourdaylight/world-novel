// ---- Novel ----
export interface NovelInfo {
  novel_id: string
  title: string
  genre: string
  db_path: string
  created_at: string
  status: string
  chapters_completed: number
  chapters_total: number
  word_count: number
  propositions: Propositions
}

export interface NovelsResponse {
  novels: NovelInfo[]
  active_novel_id: string | null
}

// ---- Story / Characters ----
export interface Character {
  id: string
  name: string
  role: string
  backstory: string
}

export interface RelationshipEdge {
  from: string
  to: string
  label: string
  trust: number
  affection: number
}

// ---- World ----
export interface WorldData {
  name?: string
  era?: string
  power_system?: any
  factions?: any[]
  locations?: any[]
  history_events?: any[]
  [key: string]: any
}

// ---- Outline / Volumes ----
export interface Volume {
  volume_index: number
  title: string
  summary: string
  theme: string
  chapter_start: number
  chapter_end: number
  arc_goal: string
}

export interface OutlineData {
  title?: string
  genre?: string
  themes?: string[]
  synopsis?: string
  [key: string]: any
}

// ---- Chapters ----
export interface ChapterInfo {
  chapter_index: number
  has_text: boolean
}

export interface ChapterScene {
  scene_index: number
  content: string
  pov_character: string
}

export interface ChapterText {
  title: string
  scenes: ChapterScene[]
  full_text: string
  summary: string
}

export interface ChapterAction {
  character_id: string
  scene_index: number
  action_type: string
  content: string
  target: string | null
}

// ---- Emotions ----
export interface EmotionState {
  chapter: number
  scene: number
  happiness: number
  anger: number
  fear: number
  sadness: number
  trust: number
  surprise: number
}

// ---- Foreshadows ----
export interface Foreshadow {
  foreshadow_id: string
  description: string
  hint_text: string
  planted_chapter: number
  expected_payoff_chapter: number
  actual_payoff_chapter: number | null
  status: string
  importance: string
  related_characters: string[]
  related_plot_thread: string | null
}

export interface PlotThread {
  thread_id: string
  name: string
  description: string
  status: string
  start_chapter: number
  key_characters: string[]
  foreshadow_ids: string[]
  chapter_progress: Record<string, any>
}

// ---- Timeline ----
export interface TimelineEra {
  era_id: string
  name: string
  description: string
  order: number
  story_time_start: string
  story_time_end: string
  chapter_start: number
  chapter_end: number
  volume_index: number
}

export interface TimelineEvent {
  event_id: string
  era_id: string
  chapter_index: number
  story_time: string
  event_type: string
  title: string
  description: string
  affected_characters: string[]
  affected_locations: string[]
  source: string
  importance: number
}

// ---- God Decisions ----
export interface GodDecision {
  decision_id: string
  chapter_index: number
  decision_type: string
  description: string
  reasoning: string
  affected_characters: string[]
  consequences: string[]
  timestamp?: string
}

// ---- Progress ----
export interface ProgressData {
  completed: number
  total: number
  phase: string
  paused: boolean
  checkpoint_id?: string
  novel_title?: string
}

export interface Checkpoint {
  checkpoint_id: string
  created_at: string
  last_completed_chapter: number
  phase: string
  novel_title: string
  total_chapters: number
  completed_chapters: number
}

// ---- Agent Files ----
export interface AgentFiles {
  character_id: string
  agent_md: string
  soul_md: string
}

// ---- Novel Full ----
export interface NovelFullChapter {
  chapter_index: number
  title: string
  text: string
  word_count: number
}

export interface NovelFull {
  title: string
  genre: string
  chapters: NovelFullChapter[]
  full_text: string
  word_count: number
}

// ---- WebSocket Events ----
export interface WSEvent {
  type: string
  [key: string]: any
}

// ---- V4: Propositions & World Creation ----
export interface Propositions {
  what_is: string
  where_from: string
  where_to: string
}

export interface CreateWorldRequest {
  title: string
  genre: string
  propositions: Propositions
  num_chapters: number
  num_characters: number
  num_volumes?: number
  theme?: string
  premise?: string
}

export interface CreateWorldResponse {
  ok: boolean
  novel_id?: string
  db_path?: string
  error?: string
}

export interface AiAnalysisResult {
  analysis: string
  conflict_points?: string[]
  suggestions: string[]
  references: string[]
}

// ---- V6: Token Stats ----
export interface TokenStats {
  total: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
  by_role: { role: string; prompt_tokens: number; completion_tokens: number; total_tokens: number }[]
  by_chapter: { chapter_index: number; total_tokens: number }[]
}

// ---- V6: Relationship History ----
export interface RelationshipHistoryEntry {
  source_id: string
  target_id: string
  relationship_type: string
  trust: number
  affection: number
  description: string
  chapter_index: number
  change_reason: string
}
