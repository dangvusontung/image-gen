import type { Concept } from '@/api/client'

export interface ConceptProgress {
  rows: Concept[]
  imageIds: string[]
  active: boolean
  failed: boolean
}

export function conceptProgress(rows: Concept[]): Map<string, ConceptProgress> {
  const grouped = new Map<string, ConceptProgress>()
  for (const row of rows) {
    const key = row.bookmark_key || `default:${row.slot}`
    const state = grouped.get(key) ?? { rows: [], imageIds: [], active: false, failed: false }
    state.rows.push(row)
    if (row.job.status === 'succeeded') state.imageIds.push(...row.job.output_asset_ids)
    state.active ||= ['queued', 'submitting', 'running'].includes(row.job.status)
    state.failed ||= row.job.status === 'failed'
    grouped.set(key, state)
  }
  for (const state of grouped.values()) {
    state.imageIds = [...new Set(state.imageIds)]
    state.rows.sort((a, b) => b.run - a.run || b.revision - a.revision)
  }
  return grouped
}

export function matchesProgress(state: ConceptProgress | undefined, filter: string): boolean {
  if (filter === 'created') return Boolean(state?.imageIds.length)
  if (filter === 'uncreated') return !state?.rows.length
  if (filter === 'active') return Boolean(state?.active)
  if (filter === 'failed') return Boolean(state?.failed && !state.active && !state.imageIds.length)
  return true
}

export function progressLabel(state: ConceptProgress | undefined): string {
  if (!state?.rows.length) return 'Chưa tạo'
  const parts = state.imageIds.length ? [`Đã tạo · ${state.imageIds.length} ảnh`] : []
  if (state.active) parts.push('Đang tạo')
  if (!parts.length) parts.push(state.failed ? 'Lỗi' : 'Đã huỷ / chưa có ảnh')
  return parts.join(' · ')
}
