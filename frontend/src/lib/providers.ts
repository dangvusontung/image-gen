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
