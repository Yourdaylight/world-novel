import client from './client'

export interface ShareMeta {
  id: string
  title: string
  author: string
  intro: string
  genre: string
  cover: string
  trial_mode: 'first_n_chapters' | 'word_count' | 'ratio'
  trial_value: number
  chapter_count: number
  word_count: number
  view_count: number
  read_count: number
  created_at: string
  share_url: string
  access: {
    authenticated: boolean
    is_owner: boolean
    level: 'anonymous' | 'registered' | 'author'
  }
}

export interface CatalogChapter {
  chapter_index: number
  title: string
  word_count: number
  readable: boolean
}

export interface ChapterContent {
  share_id: string
  chapter_index: number
  title: string
  content: string
  word_count: number
  has_prev: boolean
  has_next: boolean
  prev_index: number | null
  next_index: number | null
  authenticated: boolean
}

export async function fetchShareMeta(shareId: string): Promise<ShareMeta> {
  const { data } = await client.get(`/share/${shareId}`)
  return data
}

export async function fetchCatalog(shareId: string): Promise<{
  total: number
  trial_chapter_count: number
  authenticated: boolean
  chapters: CatalogChapter[]
}> {
  const { data } = await client.get(`/share/${shareId}/chapters`)
  return data
}

export class NeedLoginError extends Error {}

export async function fetchChapter(shareId: string, chapterIndex: number): Promise<ChapterContent> {
  try {
    const { data } = await client.get(`/share/${shareId}/chapter/${chapterIndex}`)
    return data
  } catch (e: any) {
    if (e?.response?.status === 403 && e.response?.data?.code === 'need_login') {
      throw new NeedLoginError('该章节超出试读范围')
    }
    throw e
  }
}
