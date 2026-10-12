import { describe, expect, it } from 'vitest'
import type { ModelInfo, ProviderInfo } from '@/api/client'
import { formatUsd, groupByGeneration, modelGeneration, providerStatus, referenceLimitWarning } from './providers'
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

const withId = (id: string) => ({ id, display_name: id } as ModelInfo)

describe('model generations', () => {
  it('reads a two-segment version as one generation', () => {
    expect(modelGeneration(withId('seedream-5-0-pro-260628')).label).toBe('Seedream 5.0')
    expect(modelGeneration(withId('dola-seedream-5-0-pro-260628')).label).toBe('Seedream 5.0')
    expect(modelGeneration(withId('seedream-5-0-flash-260915')).label).toBe('Seedream 5.0')
    expect(modelGeneration(withId('seedream-4-5-251128')).label).toBe('Seedream 4.5')
    expect(modelGeneration(withId('seedream-9-9-ultra-261231')).order).toBe(9.9)
  })

  it('handles single and dotted versions, and names with words before the version', () => {
    expect(modelGeneration(withId('flux-2-pro')).label).toBe('FLUX 2')
    expect(modelGeneration(withId('flux-3-image')).label).toBe('FLUX 3')
    expect(modelGeneration(withId('gemini-3-pro-image')).label).toBe('Gemini 3')
    expect(modelGeneration(withId('gemini-3.1-flash-image')).label).toBe('Gemini 3.1')
    expect(modelGeneration(withId('gemini-nano-banana-2.1')).label).toBe('Gemini Nano Banana 2.1')
  })

  it('falls back to the product name when the id carries no version', () => {
    expect(modelGeneration(withId('mock-small-refs'))).toMatchObject({ label: 'Mock', order: -1 })
    expect(modelGeneration(withId('mock-v1'))).toMatchObject({ label: 'Mock', order: -1 })
  })

  it('groups newest generation first and keeps each bucket in order', () => {
    const groups = groupByGeneration([
      withId('seedream-4-5-251128'),
      withId('seedream-5-0-pro-260628'),
      withId('mock-v1'),
      withId('seedream-5-0-flash-260915'),
      withId('seedream-4-0-250828'),
    ])
    expect(groups.map((g) => g.generation.label)).toEqual(['Seedream 5.0', 'Seedream 4.5', 'Seedream 4.0', 'Mock'])
    expect(groups[0].models.map((m) => m.id)).toEqual(['seedream-5-0-pro-260628', 'seedream-5-0-flash-260915'])
  })
})
