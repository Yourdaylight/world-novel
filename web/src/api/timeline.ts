import client from './client'
import type { TimelineEra, TimelineEvent, GodDecision } from './types'

export async function fetchTimeline(): Promise<{ eras: TimelineEra[]; events: TimelineEvent[] }> {
  const { data } = await client.get('/timeline')
  return data
}

export async function fetchGodDecisions(): Promise<{ decisions: GodDecision[] }> {
  const { data } = await client.get('/god-decisions')
  return data
}
