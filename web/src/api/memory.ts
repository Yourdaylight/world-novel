import client from './client'

export async function fetchMemoryHeat(characterId: string): Promise<any> {
  const { data } = await client.get(`/characters/${characterId}/memory-heat`)
  return data
}

export async function fetchEraSummaries(characterId: string): Promise<any> {
  const { data } = await client.get(`/characters/${characterId}/era-summaries`)
  return data
}

export async function triggerConsolidate(characterId: string): Promise<any> {
  const { data } = await client.post('/memory/consolidate', null, {
    params: { character_id: characterId },
  })
  return data
}
