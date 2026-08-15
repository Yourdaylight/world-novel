import client from './client'

// ── Types ──────────────────────────────────────────────

export interface ShareMeta {
  share_id: string
  novel_id: string
  title: string
  cover: string
  intro: string
  trial_mode: string
  trial_value: number
  created_at: string
  chapter_count?: number
  status?: string
}

export interface ShareChapterItem {
  chapter_index: number
  title: string
  word_count: number
  readable: boolean
}

export interface ShareToc {
  share_id: string
  novel_id: string
  title: string
  has_full_access: boolean
  trial_chapters: number
  volumes: { volume_index: number; title: string; chapter_start: number; chapter_end: number }[]
  chapters: ShareChapterItem[]
}

export interface ChapterBody {
  share_id: string
  novel_id: string
  chapter_index: number
  chapter_count: number
  title: string
  summary: string
  content: string
  word_count: number
}

export interface AuthorShare extends ShareMeta {
  owner_id: string
  status: 'active' | 'disabled'
  view_count: number
  read_count: number
  register_count: number
  disabled_at: string | null
  share_url: string
}

export interface BookshelfItem {
  novel_id: string
  title: string
  genre: string
  share_id: string
  chapter_index: number
  last_read_at: string
}

// ── Public reading surface ─────────────────────────────

export function getSharePage(shareId: string) {
  return client.get<ShareMeta>(`/share/${shareId}`)
}

export function getShareToc(shareId: string) {
  return client.get<ShareToc>(`/share/${shareId}/chapters`)
}

export function getShareChapter(shareId: string, chapterIndex: number) {
  return client.get<ChapterBody>(`/share/${shareId}/chapter/${chapterIndex}`)
}

export function reportConversion(shareId: string) {
  return client.post(`/share/${shareId}/conversion`, {})
}

// ── Author surface ─────────────────────────────────────

export function createShare(payload: {
  novel_id: string
  trial_mode?: string
  trial_value?: number
}) {
  return client.post('/share', payload)
}

export function listMyShares() {
  return client.get<{ shares: AuthorShare[] }>('/shares')
}

export function patchShare(
  shareId: string,
  payload: {
    trial_mode?: string
    trial_value?: number
    status?: string
    title?: string
    intro?: string
  },
) {
  return client.patch(`/share/${shareId}`, payload)
}

export function disableShare(shareId: string) {
  return client.delete(`/share/${shareId}`)
}

export function getShareStats(shareId: string, days = 30) {
  return client.get(`/share/${shareId}/stats`, { params: { days } })
}

// ── Reader surface ─────────────────────────────────────

export function getBookshelf() {
  return client.get<{ bookshelf: BookshelfItem[] }>('/bookshelf')
}

export function updateBookshelf(novelId: string, inBookshelf: boolean, shareId = '') {
  return client.put(`/bookshelf/${novelId}`, { in_bookshelf: inBookshelf, share_id: shareId })
}

export function getMyProgress(shareId: string) {
  return client.get(`/share/${shareId}/progress`)
}

export function updateMyProgress(shareId: string, chapterIndex: number) {
  return client.put(`/share/${shareId}/progress`, { chapter_index: chapterIndex })
}
