import client from './client'

// ── Types ──────────────────────────────────────────────

export interface PlatformProfile {
  platform: string
  display_name: string
  formats: string
  encoding: string
  chapter_max_words: number
  supports_volumes: number
  cover_required: number
  notes: string
}

export interface PreflightResult {
  ok: boolean
  errors: string[]
  warnings: string[]
  stats: {
    chapters: number
    total_words: number
    min_chapter_words: number
    max_chapter_words: number
    avg_chapter_words: number
    volume_count: number
    planned_chapters: number
  }
  sensitive_hits: { word: string; count: number; chapter_index: number }[]
  title: string
}

export interface PublicationRecord {
  id: string
  novel_id: string
  platform: string
  stage: 'draft' | 'exporting' | 'exported' | 'publishing' | 'published' | 'failed'
  target_book_id: string
  target_url: string
  export_meta: Record<string, unknown>
  operator: string
  created_at: string
  updated_at: string
}

// ── API ────────────────────────────────────────────────

export function getPlatforms() {
  return client.get<{ platforms: PlatformProfile[] }>('/publish/platforms')
}

export function runPreflight(novelId: string, platform = '') {
  return client.post<PreflightResult>('/publish/preflight', {
    novel_id: novelId,
    platform,
  })
}

export function exportNovel(novelId: string, platform: string) {
  return client.post(
    '/publish/export',
    { novel_id: novelId, platform },
    { responseType: 'blob', timeout: 120000 },
  )
}

export function getPublicationRecords(novelId = '') {
  return client.get<{ records: PublicationRecord[] }>('/publish/records', {
    params: novelId ? { novel_id: novelId } : {},
  })
}

export function backfillRecord(
  recordId: string,
  payload: { target_book_id?: string; target_url?: string; stage?: string },
) {
  return client.patch(`/publish/records/${recordId}`, payload)
}
