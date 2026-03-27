import client from './client'
import type { ChapterInfo, ChapterText, ChapterAction, NovelFull } from './types'

export async function fetchChapters(): Promise<{ chapters: ChapterInfo[] }> {
  const { data } = await client.get('/chapters')
  return data
}

export async function fetchChapterText(chapterIndex: number): Promise<ChapterText> {
  const { data } = await client.get(`/chapter-text/${chapterIndex}`)
  return data
}

export async function fetchChapterActions(chapterIndex: number): Promise<{ actions: ChapterAction[] }> {
  const { data } = await client.get(`/actions/${chapterIndex}`)
  return data
}

export async function fetchNovelFull(): Promise<NovelFull> {
  const { data } = await client.get('/novel-full')
  return data
}
