import client from './client'

export interface PlatformProfile {
  key: string
  name: string
  output_format: string
  encoding: string
  chapter_chars_recommended: number
  supports_volumes: boolean
  writer_url: string
  description: string
}

export interface PreflightReport {
  ok: boolean
  errors: string[]
  warnings: string[]
  stats: {
    chapter_count: number
    planned_count: number
    volume_count: number
    total_words: number
    empty_chapters: number
  }
  sensitive_hits: { word: string; count: number; chapters: number[] }[]
  platform: string | null
  novel_id?: string
  title?: string
}

export interface PublicationRecord {
  id: string
  novel_id: string
  platform: string
  stage: string
  target_book_id: string
  target_url: string
  export_meta: Record<string, any>
  operator: string
  created_at: string
  updated_at: string
}

export async function fetchPlatforms(): Promise<PlatformProfile[]> {
  const { data } = await client.get('/publish/platforms')
  return data.platforms
}

export async function runPreflight(novelId: string, platform?: string | null) {
  const { data } = await client.post<PreflightReport>('/publish/preflight', {
    novel_id: novelId,
    platform: platform ?? null,
  })
  return data
}

/** Export the novel and trigger a browser download. Returns the record id. */
export async function downloadExport(novelId: string, platform: string): Promise<string> {
  const resp = await client.post(
    '/publish/export',
    { novel_id: novelId, platform },
    { responseType: 'blob' },
  )
  const disposition = resp.headers['content-disposition'] || ''
  let filename = `${novelId}-${platform}`
  const match = /filename\*=UTF-8''(.+)$/.exec(disposition)
  if (match) {
    filename = decodeURIComponent(match[1])
  }
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return resp.headers['x-publish-record-id'] || ''
}

export async function fetchRecords(novelId: string): Promise<PublicationRecord[]> {
  const { data } = await client.get('/publish/records', { params: { novel_id: novelId } })
  return data.records
}

export async function backfillRecord(
  recordId: string,
  patch: { target_book_id?: string; target_url?: string; stage?: string },
): Promise<PublicationRecord> {
  const { data } = await client.patch(`/publish/records/${recordId}`, patch)
  return data
}
