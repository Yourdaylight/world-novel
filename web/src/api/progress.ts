import client from './client'
import type { ProgressData, Checkpoint } from './types'

export async function fetchProgress(): Promise<ProgressData> {
  const { data } = await client.get('/progress')
  return data
}

export async function fetchCheckpoints(): Promise<{ checkpoints: Checkpoint[] }> {
  const { data } = await client.get('/checkpoints')
  return data
}
