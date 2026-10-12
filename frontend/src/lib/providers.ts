import type { ModelInfo, ProviderInfo } from '@/api/client'

export function formatUsd(value: number | null): string {
  if (value === null) return 'Chưa rõ giá'
  if (value === 0) return 'Miễn phí'
  return `~$${value < 0.1 ? value.toFixed(3) : value.toFixed(2)}`
}

export function providerStatus(p: ProviderInfo): { label: string; tone: 'ok' | 'warn' | 'off' } {
  if (!p.selectable) return { label: 'Không hỗ trợ', tone: 'off' }
  if (!p.key_configured) return { label: 'Chưa có API key', tone: 'warn' }
  return { label: 'Sẵn sàng', tone: 'ok' }
}

export function referenceLimitWarning(model: ModelInfo | undefined, referenceCount: number): string | null {
  if (!model || referenceCount <= model.max_reference_images) return null
  return (
    `${model.display_name} nhận tối đa ${model.max_reference_images} ảnh tham chiếu, dự án đang có ${referenceCount}. ` +
    'Ứng dụng không tự bỏ bớt ảnh — hãy chọn model khác hoặc giảm số ảnh.'
  )
}

export const MODEL_STATUS_LABEL: Record<string, string> = {
  ga: 'Ổn định',
  preview: 'Preview',
  deprecated: 'Sắp ngừng',
}

/** Words that have their own casing rather than plain capitalisation. */
const PRODUCT_WORDS: Record<string, string> = { flux: 'FLUX', seedream: 'Seedream', seededit: 'SeedEdit' }

export interface Generation {
  key: string
  label: string
  /** Version as a number, for newest-first ordering; -1 when the id carries no version. */
  order: number
}

/**
 * The generation a model belongs to, read from its id: `seedream-5-0-pro-260628` and
 * `seedream-5-0-flash-260915` are both "Seedream 5.0", `flux-2-pro` and `flux-2-max` are
 * both "FLUX 2". Ids with no version number fall back to the product name alone.
 */
export function modelGeneration(model: ModelInfo): Generation {
  const id = model.id.toLowerCase()
  // A two-segment version (seedream-5-0-…) reads as one number; a single or dotted one (flux-2-…,
  // gemini-3.1-…, gemini-nano-banana-2.1) is already in final form.
  const match = /^([a-z][a-z-]*?)-(\d+)-(\d+)(?:-|$)/.exec(id) ?? /^([a-z][a-z-]*?)-(\d+(?:\.\d+)?)(?:-|$)/.exec(id)
  const name = (match?.[1] ?? id.split('-')[0])
    .split('-')
    .map((word) => PRODUCT_WORDS[word] ?? word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
  if (!match) return { key: name, label: name, order: -1 }
  const version = match[3] ? `${match[2]}.${match[3]}` : match[2]
  return { key: `${name} ${version}`, label: `${name} ${version}`, order: Number(version) }
}

/** Models bucketed into generations, newest generation first, each bucket in its original order. */
export function groupByGeneration(models: ModelInfo[]): { generation: Generation; models: ModelInfo[] }[] {
  const groups = new Map<string, { generation: Generation; models: ModelInfo[] }>()
  for (const model of models) {
    const generation = modelGeneration(model)
    const group = groups.get(generation.key)
    if (group) group.models.push(model)
    else groups.set(generation.key, { generation, models: [model] })
  }
  return [...groups.values()].sort(
    (a, b) => b.generation.order - a.generation.order || a.generation.label.localeCompare(b.generation.label),
  )
}
