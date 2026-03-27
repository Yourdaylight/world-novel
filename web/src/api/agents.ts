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
