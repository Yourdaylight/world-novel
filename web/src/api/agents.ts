import client from './client'
import type { AgentFiles } from './types'

export async function fetchAgentFiles(characterId: string): Promise<AgentFiles> {
  const { data } = await client.get(`/agents/${characterId}/files`)
  return data
}

export async function updateAgentSoul(characterId: string, content: string): Promise<{ ok: boolean; error?: string }> {
  const { data } = await client.put(`/agents/${characterId}/soul`, { content })
  return data
}

// ── Skills ──────────────────────────────────────────────

export interface CharacterSkill {
  character_id: string
  skill_id: string
  name: string
  category: string       // ability | habit | growth
  description: string
  trigger_conditions: string
  level: number
  direction: string
  enabled: boolean
  priority: number
  created_at: string
}

export async function fetchSkills(characterId: string): Promise<{ ok: boolean; skills: CharacterSkill[]; error?: string }> {
  const { data } = await client.get(`/agents/${characterId}/skills`)
  return data
}

export async function createSkill(
  characterId: string,
  payload: Partial<CharacterSkill>,
): Promise<{ ok: boolean; skill_id?: string; error?: string }> {
  const { data } = await client.post(`/agents/${characterId}/skills`, payload)
  return data
}

export async function updateSkill(
  characterId: string,
  skillId: string,
  payload: Partial<CharacterSkill>,
): Promise<{ ok: boolean; error?: string }> {
  const { data } = await client.put(`/agents/${characterId}/skills/${skillId}`, payload)
  return data
}

export async function deleteSkill(
  characterId: string,
  skillId: string,
): Promise<{ ok: boolean; error?: string }> {
  const { data } = await client.delete(`/agents/${characterId}/skills/${skillId}`)
  return data
}

export async function toggleSkill(
  characterId: string,
  skillId: string,
  enabled: boolean,
): Promise<{ ok: boolean; enabled: boolean; error?: string }> {
  const { data } = await client.put(`/agents/${characterId}/skills/${skillId}/toggle?enabled=${enabled}`)
  return data
}
