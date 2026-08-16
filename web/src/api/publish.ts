import client from './client'

export interface PlatformProfile {
  key: string
  label: string
  encoding: string
  chapter_word_hint: number
  volumes: boolean
  format: string
}

export interface PreflightResult {
  ok: boolean
  errors: string[]
  warnings: string[]
  sensitive_hits?: { word: string; chapter_index: number; count: number }[]
  stats: {
    chapters: number
    planned: number
    total_words: number
    volumes: number
    encoding: string
    platform: string
    platform_label: string
    has_intro: boolean
  }
}

export interface PublishRecord {
  id: string
  novel_id: string
  platform: string
  stage: string
  target_book_id: string
  target_url: string
  export_meta: Record<string, unknown>
  operator: string
  created_at: string
  updated_at?: string
}

export async function listPlatforms() {
  const { data } = await client.get('/publish/platforms')
  return data.platforms as PlatformProfile[]
}

export async function runPreflight(novelId: string, platform: string) {
  const { data } = await client.post('/publish/preflight', {
    novel_id: novelId,
    platform,
  })
  return data as PreflightResult
}

/** Export returns a binary blob; resolves with the suggested filename. */
export async function exportNovel(
  novelId: string,
  platform: string,
): Promise<{ blob: Blob; filename: string }> {
  const resp = await client.post(
    '/publish/export',
    { novel_id: novelId, platform },
    { responseType: 'blob' },
  )
  let filename = `${novelId}-${platform}.zip`
  const disposition = resp.headers['content-disposition'] || ''
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  if (star) filename = decodeURIComponent(star[1])
  return { blob: resp.data as Blob, filename }
}

export async function listRecords(novelId?: string) {
  const { data } = await client.get('/publish/records', {
    params: novelId ? { novel_id: novelId } : {},
  })
  return data.records as PublishRecord[]
}

export async function backfillRecord(
  id: string,
  patch: { target_book_id?: string; target_url?: string },
) {
  const { data } = await client.post(`/publish/records/${id}/backfill`, {
    target_book_id: patch.target_book_id || '',
    target_url: patch.target_url || '',
  })
  return data
}
