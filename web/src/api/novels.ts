import client from './client'
import type { NovelsResponse, NovelInfo, CreateWorldRequest, CreateWorldResponse, Propositions, AiAnalysisResult, SimulationBeat, SimulationProgress } from './types'

export async function fetchNovels(): Promise<NovelsResponse> {
  const { data } = await client.get('/novels')
  return data
}

export async function selectNovel(novelId: string): Promise<{ ok: boolean; active_novel_id?: string; title?: string }> {
  const { data } = await client.post('/novels/select', { novel_id: novelId })
  return data
}

export async function fetchActiveNovel(): Promise<{ active: NovelInfo | null }> {
  const { data } = await client.get('/novels/active')
  return data
}

// V4: World creation APIs

export async function createWorld(req: CreateWorldRequest): Promise<CreateWorldResponse> {
  const { data } = await client.post('/worlds/create', req)
  return data
}

export async function startGeneration(novelId: string, mode: string = 'full'): Promise<{ ok: boolean; message?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/generate`, { mode })
  return data
}

export async function fetchPropositions(novelId: string): Promise<Propositions> {
  const { data } = await client.get(`/worlds/${novelId}/propositions`)
  return data
}

export async function saveWorld(world: any, novelId?: string): Promise<{ ok: boolean }> {
  const params = novelId ? { novel_id: novelId } : {}
  const { data } = await client.put('/world', { world }, { params })
  return data
}

export async function analyzeProposition(step: number, text: string, context: Partial<Propositions> = {}): Promise<AiAnalysisResult> {
  const { data } = await client.post('/ai/analyze-proposition', { step, text, context })
  return data
}

export async function deleteWorld(novelId: string): Promise<{ ok: boolean }> {
  const { data } = await client.delete(`/worlds/${novelId}`)
  return data
}

export async function resumeGeneration(novelId: string, mode: string = 'full', guidance?: string): Promise<{ ok: boolean; message?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/resume`, { mode, guidance })
  return data
}

export async function pauseGeneration(novelId: string): Promise<{ ok: boolean; message?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/pause`)
  return data
}

export async function rewriteChapter(
  novelId: string,
  chapterIndex: number,
  guidance: string = ''
): Promise<{ ok: boolean; word_count?: number; title?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/rewrite-chapter`, {
    chapter_index: chapterIndex,
    guidance,
  })
  return data
}

export async function writeChapter(
  novelId: string,
  chapterIndex: number,
  guidance: string = ''
): Promise<{ ok: boolean; word_count?: number; title?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/write-chapter`, {
    chapter_index: chapterIndex,
    guidance,
  })
  return data
}

// ======================================================================
// V9: Decoupled pipeline — Preparation + Simulation APIs
// ======================================================================

export async function startPreparation(novelId: string, mode: string = 'full'): Promise<{ ok: boolean; message?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/prepare`, { mode })
  return data
}

export async function startSimulation(novelId: string): Promise<{ ok: boolean; message?: string; beat_count?: number; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/simulate`)
  return data
}

export async function stopSimulation(novelId: string): Promise<{ ok: boolean; message?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/stop-simulation`)
  return data
}

export async function fetchSimulationProgress(novelId: string): Promise<SimulationProgress> {
  const { data } = await client.get(`/worlds/${novelId}/simulation-progress`)
  return data
}

export async function fetchSimulationBeats(novelId: string): Promise<{ beats: SimulationBeat[]; total: number }> {
  const { data } = await client.get(`/worlds/${novelId}/simulation-beats`)
  return data
}
