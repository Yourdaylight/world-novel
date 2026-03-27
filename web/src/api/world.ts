import client from './client'
import type { WorldData, OutlineData, Volume } from './types'

export async function fetchWorld(): Promise<{ world: WorldData | null }> {
  const { data } = await client.get('/world')
  return data
}

export async function fetchOutline(): Promise<{ outline: OutlineData | null; volumes: Volume[] }> {
  const { data } = await client.get('/outline')
  return data
}
