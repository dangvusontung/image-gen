import type { AssetKind } from '@/api/client'

// Mirrors backend limits in app/routes/assets.py and app/config.py; the server stays authoritative.
export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const MAX_FILE_BYTES = 20 * 1024 * 1024
export const LIMITS: Record<AssetKind, number> = { reference: 8, side_profile: 4, template: 8 }
export const RECOMMENDED_MIN_REFERENCES = 3

export interface PrevalidationResult {
  accepted: File[]
  errors: string[]
}

export function prevalidateFiles(files: File[], kind: AssetKind, existingCount: number): PrevalidationResult {
  const errors: string[] = []
  const valid = files.filter((f) => {
    if (!ACCEPTED_TYPES.includes(f.type)) {
      errors.push(`${f.name}: chỉ hỗ trợ JPEG, PNG, WEBP`)
      return false
    }
    if (f.size > MAX_FILE_BYTES) {
      errors.push(`${f.name}: vượt quá ${MAX_FILE_BYTES / 1024 / 1024}MB`)
      return false
    }
    return true
  })
  const room = Math.max(0, LIMITS[kind] - existingCount)
  if (valid.length > room) {
    errors.push(`Tối đa ${LIMITS[kind]} ảnh loại này — bỏ qua ${valid.length - room} ảnh`)
  }
  return { accepted: valid.slice(0, room), errors }
}

export function referenceCountWarning(count: number): string | null {
  if (count === 0) return null
  if (count < RECOMMENDED_MIN_REFERENCES) {
    return `Mới có ${count} ảnh. Nên dùng 3–8 ảnh ở nhiều góc để giữ nhận diện khuôn mặt tốt hơn.`
  }
  return null
}

export function moveItem<T>(items: T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length || from === to) return items
  const next = [...items]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
