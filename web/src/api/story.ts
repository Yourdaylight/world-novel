import client from './client'
import type { Character, RelationshipEdge, GraphData, GraphPath } from './types'

export async function fetchStory(): Promise<{ characters: Character[] }> {
  const { data } = await client.get('/story')
  return data
}

export async function fetchRelationships(): Promise<{ edges: RelationshipEdge[] }> {
  const { data } = await client.get('/relationships')
  return data
}

// V10: Neo4j graph queries

export async function fetchGraphData(): Promise<GraphData> {
  const { data } = await client.get('/graph/relationships')
  return data
}

export async function fetchGraphPath(fromId: string, toId: string): Promise<{ paths: any[] }> {
  const { data } = await client.get('/graph/path', { params: { from: fromId, to: toId } })
  return data
}

export async function fetchSocialContext(characterId: string): Promise<{ context: string }> {
  const { data } = await client.get(`/graph/social-context/${characterId}`)
  return data
}
