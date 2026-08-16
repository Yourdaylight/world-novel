import client from './client'
import { publicClient } from './public'

// ── Author-side management (authenticated workbench client) ──

export interface ShareLink {
  id: string
  novel_id: string
  owner_id: string
  title_snapshot: string
  intro_snapshot: string
  genre_snapshot: string
  trial_mode: string
  trial_value: number
  status: string
  view_count: number
  read_count: number
  created_at: string
  disabled_at: string | null
}

export async function createShare(input: {
  novel_id: string
  trial_mode?: string
  trial_value?: number
}) {
  const { data } = await client.post('/share', {
    novel_id: input.novel_id,
    trial_mode: input.trial_mode ?? 'first_n_chapters',
    trial_value: input.trial_value ?? 3,
  })
  return data as { ok: boolean; id: string; share_url: string; created: boolean }
}

export async function listMyShares() {
  const { data } = await client.get('/shares')
  return data.shares as ShareLink[]
}

export async function patchShare(
  id: string,
  patch: { trial_mode?: string; trial_value?: number; status?: string },
) {
  const { data } = await client.patch(`/share/${id}`, patch)
  return data
}

// ── Public reader (bare client, no workbench interceptors) ──

export interface ReaderMeta {
  id: string
  title: string
  intro: string
  genre: string
  trial_mode: string
  trial_value: number
  trial_open_chapters: number | null
  chapters_total: number
  authed: boolean
  can_read_all: boolean
  stats: { views: number; reads: number }
}

export interface TocChapter {
  index: number
  title: string
  words: number
  readable: boolean
}

export interface ChapterContent {
  index: number
  title: string
  content: string
  words: number
  has_prev: boolean
  has_next: boolean
  next_readable: boolean | null
  authed: boolean
}

export async function fetchShareMeta(id: string) {
  const { data } = await publicClient.get(`/share/${id}`)
  return data as ReaderMeta
}

export async function fetchToc(id: string) {
  const { data } = await publicClient.get(`/share/${id}/chapters`)
  return data.chapters as TocChapter[]
}

export async function fetchChapter(id: string, index: number) {
  const { data } = await publicClient.get(`/share/${id}/chapter/${index}`)
  return data as ChapterContent
}

/** Invite-code login (jwt mode) — registration-free, the invite code is the identity. */
export async function readerLogin(inviteCode: string) {
  const { data } = await publicClient.post('/auth/login', { invite_code: inviteCode })
  return data as { access_token: string; code: string }
}

export async function fetchAuthConfig() {
  const { data } = await publicClient.get('/auth/config')
  return data as { mode: string; oauth_login_url?: string; login_url?: string }
}
