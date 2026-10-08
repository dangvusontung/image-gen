import { describe, expect, it } from 'vitest'
import type { ModelInfo, ProviderInfo } from '@/api/client'
import { formatUsd, providerStatus, referenceLimitWarning } from './providers'
import { parseRoute } from './useHashRoute'

const model = { id: 'm', display_name: 'M', max_reference_images: 8 } as ModelInfo
const provider = (o: Partial<ProviderInfo>) => ({ selectable: true, key_configured: true, ...o }) as ProviderInfo

describe('provider helpers', () => {
  it('formats prices', () => {
    expect(formatUsd(null)).toBe('Chưa rõ giá')
    expect(formatUsd(0)).toBe('Miễn phí')
    expect(formatUsd(0.0504)).toBe('~$0.050')
    expect(formatUsd(0.134)).toBe('~$0.13')
  })

  it('derives status', () => {
    expect(providerStatus(provider({})).tone).toBe('ok')
    expect(providerStatus(provider({ key_configured: false })).label).toBe('Chưa có API key')
    expect(providerStatus(provider({ selectable: false })).tone).toBe('off')
  })

  it('warns only when references exceed the model limit', () => {
    expect(referenceLimitWarning(model, 8)).toBeNull()
    expect(referenceLimitWarning(model, 9)).toMatch(/tối đa 8.*có 9.*không tự bỏ bớt/)
    expect(referenceLimitWarning(undefined, 99)).toBeNull()
  })
})

describe('parseRoute', () => {
  it('maps hashes to pages', () => {
    expect(parseRoute('')).toEqual({ page: 'dashboard' })
    expect(parseRoute('#/settings')).toEqual({ page: 'settings' })
    expect(parseRoute('#/projects/abc-1')).toEqual({ page: 'project', projectId: 'abc-1' })
  })
})
