import client from './client'
import type { Foreshadow, PlotThread } from './types'

export async function fetchForeshadows(): Promise<{ foreshadows: Foreshadow[] }> {
  const { data } = await client.get('/foreshadows')
  return data
}

export async function fetchPlotThreads(): Promise<{ plot_threads: PlotThread[] }> {
  const { data } = await client.get('/plot-threads')
  return data
}
