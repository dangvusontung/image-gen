import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { request, type ProjectDetail } from '@/api/client'
import ModelPicker from './ModelPicker'

vi.mock('@/api/client', () => ({
  request: vi.fn(),
  useProviders: () => ({ isPending: false, error: null, data: [
    { name: 'mock', display_name: 'Mock', selectable: true, enabled: true, models: [{ id: 'mock-v1', display_name: 'Mock v1', aspect_ratios: ['1:1'], max_reference_images: 14 }] },
    { name: 'gemini', display_name: 'Gemini', selectable: true, enabled: true, models: [
      { id: 'image-pro', display_name: 'Image Pro', aspect_ratios: ['1:1'], max_reference_images: 8 },
      { id: 'image-pro-preview', display_name: 'Image Pro', aspect_ratios: ['1:1'], max_reference_images: 8 },
      { id: 'text-only-image', display_name: 'No references', aspect_ratios: ['1:1'], max_reference_images: 0 },
    ] },
    { name: 'unconfigured', display_name: 'Unconfigured', selectable: true, enabled: false, models: [{ id: 'locked-model', display_name: 'Locked model', aspect_ratios: ['1:1'], max_reference_images: 8 }] },
  ] }),
}))
const project = { id: 'pack', provider: 'mock', model: 'mock-v1' } as ProjectDetail
const onChange = vi.fn().mockResolvedValue(undefined)
beforeEach(() => { vi.mocked(request).mockReset().mockResolvedValue({}); onChange.mockClear() })
afterEach(cleanup)

it('switches provider and model together directly from the model list', async () => {
  render(<ModelPicker project={project} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('Generation model'), { target: { value: JSON.stringify(['gemini', 'image-pro-preview']) } })
  await waitFor(() => expect(onChange).toHaveBeenCalledOnce())
  const [path, init] = vi.mocked(request).mock.calls[0]
  expect(path).toBe('/projects/pack')
  expect(JSON.parse(init!.body as string)).toEqual({ provider: 'gemini', model: 'image-pro-preview' })
  expect(screen.getByRole('option', { name: 'Image Pro · image-pro' })).toBeEnabled()
  expect(screen.getByRole('option', { name: 'Image Pro · image-pro-preview' })).toBeEnabled()
})

it('disables unconfigured providers and models that cannot take character references', () => {
  render(<ModelPicker project={project} onChange={onChange} />)
  expect(screen.getByRole('option', { name: /Locked model/ })).toBeDisabled()
  expect(screen.getByRole('option', { name: /No references/ })).toBeDisabled()
})

it('shows a save error and keeps the previous selection', async () => {
  vi.mocked(request).mockRejectedValueOnce(new Error('Could not save model'))
  render(<ModelPicker project={project} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('Generation model'), { target: { value: JSON.stringify(['gemini', 'image-pro']) } })
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not save model'))
  expect(screen.getByLabelText('Generation model')).toHaveValue(JSON.stringify(['mock', 'mock-v1']))
  expect(onChange).not.toHaveBeenCalled()
})
