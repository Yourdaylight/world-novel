import client from './client'
import type { NovelsResponse, NovelInfo, CreateWorldRequest, CreateWorldResponse, Propositions, AiAnalysisResult } from './types'

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

export async function resumeGeneration(novelId: string, mode: string = 'full'): Promise<{ ok: boolean; message?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/resume`, { mode })
  return data
}

export async function pauseGeneration(novelId: string): Promise<{ ok: boolean; message?: string; error?: string }> {
  const { data } = await client.post(`/worlds/${novelId}/pause`)
  return data
}
