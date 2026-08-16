import client from './client'

export type TrialMode = 'first_n_chapters' | 'word_count' | 'ratio'

export interface ShareMeta {
  id: string
  title: string
  intro: string
  cover: string
  genre: string
  author: string
  chapters_total: number
  trial_mode: TrialMode
  trial_value: number
  view_count: number
  read_count: number
  authenticated: boolean
  can_read_full: boolean
}

export interface TocChapter {
  chapter_index: number
  title: string
  word_count: number
  readable: boolean
}

export interface ShareChapter {
  chapter_index: number
  title: string
  text: string
  word_count: number
  authenticated: boolean
  next_locked: boolean
}

export interface OwnerShare {
  id: string
  novel_id: string
  title: string
  status: 'active' | 'disabled'
  trial_mode: TrialMode
  trial_value: number
  view_count: number
  read_count: number
  created_at: string
  disabled_at?: string | null
  genre: string
  chapters_total: number
}

// ── Public reader surface (no auth required) ──────────────────────────────

export async function fetchShareMeta(shareId: string): Promise<ShareMeta> {
  const { data } = await client.get(`/share/${shareId}`)
  return data
}

export async function fetchShareChapters(shareId: string): Promise<{ meta: ShareMeta; chapters: TocChapter[] }> {
  const { data } = await client.get(`/share/${shareId}/chapters`)
  return data
}

/** Throws an axios error whose response.status === 403 when beyond the trial. */
export async function fetchShareChapter(shareId: string, chapterIndex: number): Promise<ShareChapter> {
  const { data } = await client.get(`/share/${shareId}/chapter/${chapterIndex}`)
  return data
}

// ── Author management (auth required) ────────────────────────────────────

export async function createShare(
  novelId: string,
  trial: { trial_mode: TrialMode; trial_value: number },
): Promise<{ share: OwnerShare; reused?: boolean }> {
  const { data } = await client.post('/share', { novel_id: novelId, ...trial })
  return data
}

export async function listMyShares(): Promise<OwnerShare[]> {
  const { data } = await client.get('/shares/mine')
  return data.shares || []
}

export async function updateShare(
  shareId: string,
  patch: Partial<{ trial_mode: TrialMode; trial_value: number; status: 'active' | 'disabled' }>,
): Promise<{ share: OwnerShare }> {
  const { data } = await client.patch(`/share/${shareId}`, patch)
  return data
}
