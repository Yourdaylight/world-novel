import client from './client'
import type { Character, RelationshipEdge } from './types'

export async function fetchStory(): Promise<{ characters: Character[] }> {
  const { data } = await client.get('/story')
  return data
}

export async function fetchRelationships(): Promise<{ edges: RelationshipEdge[] }> {
  const { data } = await client.get('/relationships')
  return data
}
