import client from './client'

export interface PreflightChapterStat {
  chapter_index: number
  title: string
  word_count: number
}

export interface PreflightVerdict {
  ok: boolean
  errors: { code: string; message: string; indices?: number[] }[]
  warnings: { code: string; message: string; indices?: number[] }[]
  sensitive: { word: string; count: number; chapter_index: number; samples: string[] }[]
  stats: {
    platform: string
    chapters: number
    volumes: number
    total_words: number
    missing_indices: number[]
    empty_indices: number[]
    per_chapter: PreflightChapterStat[]
  }
}

export interface PlatformOption {
  key: string
  label: string
  description: string
}

// Mirrors PLATFORMS in src/novel_creator/web/platforms.py
export const PLATFORM_OPTIONS: PlatformOption[] = [
  { key: 'bundle', label: '全格式打包 ZIP', description: '番茄/七猫/EPUB/Word 一次打包（推荐）' },
  { key: 'fanqie', label: '番茄小说', description: 'TXT · GB18030 编码，作家助手上传' },
  { key: 'qimao', label: '七猫小说', description: 'TXT · UTF-8，保留分卷结构' },
  { key: 'epub', label: 'EPUB 电子书', description: 'Apple Books / 多看通用' },
  { key: 'rtf', label: 'Word (RTF)', description: 'Word 直接打开' },
  { key: 'txt', label: '通用 TXT', description: 'UTF-8 纯文本' },
]

export interface PublicationRecord {
  id: string
  novel_id: string
  platform: string
  stage: string
  target_book_id?: string
  target_url?: string
  export_meta: Record<string, unknown>
  operator: string
  created_at: string
}

export async function runPreflight(novelId: string, platform = 'fanqie'): Promise<PreflightVerdict> {
  const { data } = await client.post('/publish/preflight', null, {
    params: { novel_id: novelId, platform },
  })
  return data
}

/** Trigger an export and save the returned file via the browser. */
export async function exportNovel(novelId: string, platform: string): Promise<void> {
  const resp = await client.post(
    '/publish/export',
    { novel_id: novelId, platform },
    { responseType: 'blob' },
  )
  // Filename from Content-Disposition when present (filename*=UTF-8''...).
  let filename = `novel-${platform}`
  const disp = resp.headers['content-disposition'] || ''
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disp)
  if (star) filename = decodeURIComponent(star[1])
  const blob = new Blob([resp.data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function listRecords(novelId: string): Promise<PublicationRecord[]> {
  const { data } = await client.get('/publish/records', { params: { novel_id: novelId } })
  return data.records || []
}

export async function backfillRecord(
  recordId: string,
  payload: { target_book_id?: string; target_url?: string },
): Promise<void> {
  await client.post(`/publish/records/${recordId}/backfill`, payload)
}
