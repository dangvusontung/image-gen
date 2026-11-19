import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { ProjectDetail } from '@/api/client'
import MasterOutfitEdit, { MasterOutfitDetailAction } from './MasterOutfitEdit'

afterEach(() => vi.unstubAllGlobals())
it('uploads a pasted outfit and edits the existing Master only after confirmation', async () => {
  const user = userEvent.setup()
  const onClose = vi.fn()
  const calls: { url: string; init?: RequestInit }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (url.endsWith('/assets')) return Response.json([{ id: 'pasted', filename: 'outfit.png', kind: 'template', selected: true }])
    return Response.json({ job_ids: ['edited'] })
  }))
  const project = { id: 'p', rights_confirmed: true, assets: [{ id: 'reference', filename: 'face.png', kind: 'reference', selected: false }] } as ProjectDetail
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MasterOutfitEdit project={project} masterId="master" masterAssetId="source" onClose={onClose} />
  </QueryClientProvider>)
  const generate = screen.getByRole('button', { name: 'Tạo Master với outfit mới' })
  expect(generate).toBeDisabled()
  fireEvent.paste(screen.getByRole('region', { name: 'Đổi outfit Master' }), { clipboardData: { files: [new File(['image'], 'outfit.png', { type: 'image/png' })] } })
  await waitFor(() => expect(screen.getByAltText('Outfit được chọn')).toHaveAttribute('src', '/api/assets/pasted/content'))
  const upload = calls.find(call => call.url.endsWith('/assets'))!
  expect((upload.init?.body as FormData).get('kind')).toBe('template')
  expect(generate).toBeDisabled()
  expect(calls.some(call => call.url.endsWith('/outfit'))).toBe(false)
  await user.click(screen.getByRole('checkbox'))
  await user.click(generate)
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
  const edit = calls.find(call => call.url.endsWith('/master/master/outfit'))!
  expect(JSON.parse(String(edit.init?.body))).toEqual({ outfit_reference_asset_id: 'pasted', confirmed: true })
  expect(calls.some(call => call.url.endsWith('/approve'))).toBe(false)
})


it('edits the Master being viewed rather than the approved Master', async () => {
  const user = userEvent.setup()
  const mutations: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') { mutations.push(url); return Response.json({ job_ids: ['edited'] }) }
    if (url.endsWith('/workflow')) return Response.json({ approved_master_id: 'new', masters: [
      { id: 'new', job: { status: 'succeeded', output_asset_ids: ['new-photo'] } },
      { id: 'old', job: { status: 'succeeded', output_asset_ids: ['old-photo'] } },
    ] })
    return Response.json({ id: 'p', rights_confirmed: true, assets: [{ id: 'reference', filename: 'outfit.png', kind: 'reference', selected: true }] })
  }))
  render(<QueryClientProvider client={new QueryClient()}><MasterOutfitDetailAction projectId="p" assetId="old-photo" /></QueryClientProvider>)
  await user.click(screen.getByRole('button', { name: 'Đổi outfit Master' }))
  expect(await screen.findByAltText('Master nguồn')).toHaveAttribute('src', '/api/assets/old-photo/content')
  await user.click(screen.getByRole('button', { name: 'Chọn outfit outfit.png' }))
  await user.click(screen.getByRole('checkbox'))
  await user.click(screen.getByRole('button', { name: 'Tạo Master với outfit mới' }))
  await waitFor(() => expect(mutations).toEqual(['/api/projects/p/master/old/outfit']))
})


it('offers presets in outfit editing and sends only the selected preset', async () => {
  const user = userEvent.setup()
  const payloads: unknown[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/master/outfit-options')) return Response.json({ outfit: [['tank_pleated_classic', 'Tank trắng + mini xếp ly xám']] })
    if (init?.method === 'POST') payloads.push(JSON.parse(String(init.body)))
    return Response.json({ job_ids: ['edited'] })
  }))
  const project = { id: 'p', rights_confirmed: true, assets: [{ id: 'photo', filename: 'outfit.png', kind: 'reference', selected: true }] } as ProjectDetail
  render(<QueryClientProvider client={new QueryClient()}><MasterOutfitEdit project={project} masterId="master" masterAssetId="source" onClose={vi.fn()} /></QueryClientProvider>)
  await user.click(screen.getByRole('button', { name: 'Chọn outfit outfit.png' }))
  await user.click(screen.getByRole('checkbox'))
  await waitFor(() => expect(screen.getByLabelText('Preset đổi outfit Master')).toBeEnabled())
  await user.selectOptions(screen.getByLabelText('Preset đổi outfit Master'), 'tank_pleated_classic')
  expect(screen.getByRole('checkbox')).not.toBeChecked()
  expect(screen.queryByAltText('Outfit được chọn')).not.toBeInTheDocument()
  expect(screen.getByText(/gửi 1 ảnh tới nhà cung cấp/)).toBeInTheDocument()
  await user.click(screen.getByRole('checkbox'))
  await user.click(screen.getByRole('button', { name: 'Tạo Master với outfit mới' }))
  await waitFor(() => expect(payloads).toEqual([{ master_outfit: { outfit: 'tank_pleated_classic', custom_outfit: '' }, confirmed: true }]))
})
