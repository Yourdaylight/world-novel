import client from './client'

export type TrialMode = 'first_n_chapters' | 'word_count' | 'ratio'

export interface ShareLink {
  id: string
  novel_id: string
  owner_id: string
  title: string
  author: string
  intro: string
  genre: string
  cover: string
  trial_mode: TrialMode
  trial_value: number
  status: 'active' | 'disabled'
  view_count: number
  read_count: number
  chapter_count: number
  word_count: number
  created_at: string
  updated_at: string
  share_url?: string
}

export async function createShare(
  novelId: string,
  trialMode: TrialMode = 'first_n_chapters',
  trialValue = 3,
): Promise<ShareLink> {
  const { data } = await client.post('/share', {
    novel_id: novelId,
    trial_mode: trialMode,
    trial_value: trialValue,
  })
  return data
}

export async function fetchMyShares(): Promise<ShareLink[]> {
  const { data } = await client.get('/share/mine')
  return data.shares
}

export async function updateShare(
  shareId: string,
  patch: { trial_mode?: TrialMode; trial_value?: number; status?: 'active' | 'disabled' },
): Promise<ShareLink> {
  const { data } = await client.patch(`/share/${shareId}`, patch)
  return data
}
