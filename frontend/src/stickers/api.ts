import { request, type GenerationJob, type ProjectDetail } from '@/api/client'
import { apiUrl } from '@/lib/backend'

export interface StickerItem {
  id: string; expression: string; caption: string; emoji: string
  text_style?: 'caption' | 'speech' | 'thought'
  text_x?: number; text_y?: number; text_size?: number; text_color?: string
}
export interface PackSummary { id: string; name: string; style: string; count: number; reference_id: string | null }
export interface Pack {
  id: string; name: string; publisher: string; style: string; items: StickerItem[]
  project: ProjectDetail; jobs: Record<string, GenerationJob>
  concept_brief: string
  approved_concept: GenerationJob | null
  concepts: { job: GenerationJob; current: boolean }[]
}
export interface Estimate { total_usd: number | null; per_image_usd: number | null; size: string | null }
export const json = (method: string, data: unknown) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
export const packRequest = <T,>(path = '', init?: RequestInit) => request<T>(`/sticker-packs${path}`, init)
export const previewUrl = (pack: Pack, item: StickerItem) => apiUrl(`/sticker-packs/${pack.id}/stickers/${item.id}/image?job_id=${pack.jobs[item.id]?.id}&v=${encodeURIComponent(JSON.stringify(item))}`)
export const activeJob = (job?: GenerationJob) => !!job && ['queued', 'submitting', 'running'].includes(job.status)
export function freshJob(pack: Pack, item: StickerItem) {
  const job = pack.jobs[item.id]
  const snapshot = job?.meta.sticker_item as StickerItem | undefined
  return !!pack.approved_concept && job?.status === 'succeeded' && job.meta.concept_job_id === pack.approved_concept.id && job.meta.artwork_version === 2 && job.meta.style === pack.style && snapshot?.expression === item.expression
}
