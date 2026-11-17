import { afterEach, expect, it, vi } from 'vitest'
import { api } from './client'

afterEach(() => vi.unstubAllGlobals())

it('omits Mock from the provider choices while keeping real providers', async () => {
  const providers = [{ name: 'mock', models: [{ id: 'mock-v1' }] }, { name: 'gemini', models: [] }]
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => providers }))
  expect(await api.listProviders()).toEqual([providers[1]])
})
